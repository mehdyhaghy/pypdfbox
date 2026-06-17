import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDTerminalField;

/**
 * Live oracle probe for the BYTE-LEVEL text-show payload a TEXT-FIELD's
 * /AP /N appearance stream carries after PDTextField.setValue regeneration.
 *
 * Where the sibling TextFieldApProbe pins the structural skeleton + the
 * *decoded* shown string, this probe pins the EXACT bytes of the shown
 * literal — the value emitted through the font encoder — so a divergence in
 * how the /DA font (Helvetica / WinAnsiEncoding) maps a non-ASCII codepoint
 * to a single-byte code is caught at the token level. A decoded comparison
 * would mask such a divergence (both decode back to the same Unicode), but a
 * viewer renders the BYTES against the font's encoding, so the bytes must
 * match for true appearance parity.
 *
 * Two modes (same contract as TextFieldApProbe):
 *
 *   set:  java TextFieldApTokenProbe set in.pdf out.pdf name=value [...]
 *         Re-runs setValue through upstream PDFBox so it composes its own
 *         appearance into the identical field configuration, then saves.
 *
 *   read: java TextFieldApTokenProbe read in.pdf name [name ...]
 *         Emits, per field, one LF-terminated tab-separated record:
 *
 *           fqName \t tfSize \t tjHex \t tdY
 *
 *         where:
 *           - tfSize = the resolved Tf font size (the /DA size, or the
 *                      auto-size PDFBox picked), formatted %.2f
 *           - tjHex  = the lowercase hex of the concatenated bytes of every
 *                      Tj / TJ literal shown (the exact encoded payload)
 *           - tdY    = the integer-rounded y of the first text-positioning
 *                      operator (Td / Tm) — the baseline placement
 */
public final class TextFieldApTokenProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("set".equals(mode)) {
            doSet(args);
        } else if ("read".equals(mode)) {
            doRead(args, out);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void doSet(String[] args) throws Exception {
        File in = new File(args[1]);
        File outFile = new File(args[2]);
        try (PDDocument doc = Loader.loadPDF(in)) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDAcroForm form = catalog.getAcroForm();
            for (int i = 3; i < args.length; i++) {
                int eq = args[i].indexOf('=');
                String name = args[i].substring(0, eq);
                String value = args[i].substring(eq + 1);
                PDField field = form.getField(name);
                if (field instanceof PDTerminalField) {
                    field.setValue(value);
                }
            }
            doc.save(outFile);
        }
    }

    private static void doRead(String[] args, PrintStream out) throws Exception {
        File in = new File(args[1]);
        try (PDDocument doc = Loader.loadPDF(in)) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDAcroForm form = catalog.getAcroForm();
            StringBuilder sb = new StringBuilder();
            for (int i = 2; i < args.length; i++) {
                String name = args[i];
                PDField field = form.getField(name);
                if (field == null) {
                    sb.append(name).append("\t0\t\t0\n");
                    continue;
                }
                sb.append(line(field)).append('\n');
            }
            out.print(sb);
        }
    }

    private static String line(PDField field) throws Exception {
        String name = field.getFullyQualifiedName();
        double tfSize = 0.0;
        StringBuilder tjHex = new StringBuilder();
        long tdY = 0;
        boolean haveSize = false;
        boolean haveY = false;

        if (field instanceof PDTerminalField) {
            for (PDAnnotationWidget widget : ((PDTerminalField) field).getWidgets()) {
                PDAppearanceDictionary ap = widget.getAppearance();
                if (ap == null) {
                    continue;
                }
                PDAppearanceEntry normal = ap.getNormalAppearance();
                if (normal == null || !normal.isStream()) {
                    continue;
                }
                PDAppearanceStream stream = normal.getAppearanceStream();
                PDFStreamParser parser =
                        new PDFStreamParser(new PDAppearanceStream(stream.getCOSObject()));
                List<COSBase> operands = new ArrayList<>();
                for (Object token = parser.parseNextToken();
                        token != null;
                        token = parser.parseNextToken()) {
                    if (token instanceof Operator) {
                        String op = ((Operator) token).getName();
                        if ("Tf".equals(op) && operands.size() >= 2 && !haveSize) {
                            tfSize = numOf(operands.get(operands.size() - 1));
                            haveSize = true;
                        } else if (("Td".equals(op) || "TD".equals(op))
                                && operands.size() >= 2 && !haveY) {
                            tdY = Math.round(numOf(operands.get(operands.size() - 1)));
                            haveY = true;
                        } else if ("Tm".equals(op) && operands.size() >= 6 && !haveY) {
                            tdY = Math.round(numOf(operands.get(5)));
                            haveY = true;
                        } else if ("Tj".equals(op) || "'".equals(op) || "\"".equals(op)) {
                            if (!operands.isEmpty()) {
                                COSBase last = operands.get(operands.size() - 1);
                                if (last instanceof COSString) {
                                    appendHex(tjHex, ((COSString) last).getBytes());
                                }
                            }
                        } else if ("TJ".equals(op)) {
                            if (!operands.isEmpty()
                                    && operands.get(operands.size() - 1) instanceof COSArray) {
                                COSArray arr =
                                        (COSArray) operands.get(operands.size() - 1);
                                for (COSBase el : arr) {
                                    if (el instanceof COSString) {
                                        appendHex(tjHex, ((COSString) el).getBytes());
                                    }
                                }
                            }
                        }
                        operands.clear();
                    } else if (token instanceof COSBase) {
                        operands.add((COSBase) token);
                    }
                }
                break;
            }
        }
        return name + "\t" + fmt(tfSize) + "\t" + tjHex + "\t" + tdY;
    }

    private static void appendHex(StringBuilder sb, byte[] bytes) {
        for (byte b : bytes) {
            sb.append(String.format(Locale.ROOT, "%02x", b & 0xff));
        }
    }

    private static double numOf(COSBase b) {
        if (b instanceof COSNumber) {
            return ((COSNumber) b).floatValue();
        }
        return 0.0;
    }

    private static String fmt(double d) {
        return String.format(Locale.ROOT, "%.2f", d);
    }
}
