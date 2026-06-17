import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.Loader;
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
 * Live oracle probe for AcroForm FIELD-APPEARANCE GENERATION under MALFORMED /DA
 * strings and edge field configurations.
 *
 * Where the sibling {@code TextFieldApProbe} pins the structural skeleton for a
 * handful of WELL-FORMED /DA strings, this probe fuzzes the /DA tokenizer and
 * appearance generator with the hostile / degenerate subset a buggy producer
 * emits: empty /DA, missing the {@code Tf} font operator, font size 0 (auto),
 * NEGATIVE size, unknown font name, multiple {@code Tf} ops, the colour given as
 * {@code g} / {@code rg} / {@code k}, interleaved garbage tokens, field values
 * with newlines (multiline on/off), /Q quadding 0/1/2/garbage, a /DR missing the
 * font the /DA references, and a comb field with /MaxLen.
 *
 * Contract: the test BUILDS the fuzz corpus through pypdfbox and saves it; this
 * probe then re-runs {@code setValue} through upstream PDFBox so PDFBox composes
 * ITS OWN appearance into the identical field configuration, then projects a
 * STABLE shape of the generated /AP /N stream — never exact bytes.
 *
 * Two modes (same set/read split as {@code TextFieldApProbe}):
 *
 *   set:  java AppearanceGenFuzzProbe set in.pdf out.pdf name=value [name=value ...]
 *         Re-runs setValue through upstream PDFBox into the identical fields,
 *         then saves.
 *
 *   read: java AppearanceGenFuzzProbe read in.pdf name [name ...]
 *         Emits, per field, one LF-terminated tab-separated record:
 *
 *           fqName \t da \t ops \t facts
 *
 *         where:
 *           - da    = the resolved /DA string (field, falling back to AcroForm),
 *                     or "none"
 *           - ops   = comma-joined operator-name sequence over the widget's
 *                     normal-appearance content stream (the structural skeleton)
 *           - facts = semicolon-joined key=value tokens projecting the STABLE
 *                     shape:
 *                       tf=<fontResName>/<size>  the Tf font alias + size (%.2f)
 *                       col=<op>:<n>             non-stroking colour operator
 *                                                (g/rg/k) + component count, or
 *                                                "none"
 *                       shows=<count>            number of Tj / TJ / ' / "
 *                       lines=<count>            distinct rounded baselines
 *                       text=<concatdecoded>     the concatenated decoded shown
 *                                                text (newlines -> "|")
 *                     A field with NO generated appearance stream emits
 *                     "noap".
 */
public final class AppearanceGenFuzzProbe {

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
                String value = args[i].substring(eq + 1).replace("\\n", "\n");
                PDField field = form.getField(name);
                if (field instanceof PDTerminalField) {
                    try {
                        field.setValue(value);
                    } catch (Exception e) {
                        // Some malformed /DA make upstream throw at appearance
                        // composition time; the read side will report "noap".
                    }
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
                    sb.append(name).append("\tnone\t\tnofield\n");
                    continue;
                }
                sb.append(line(field)).append('\n');
            }
            out.print(sb);
        }
    }

    private static String line(PDField field) throws Exception {
        String name = field.getFullyQualifiedName();
        String da = resolveDa(field);

        if (!(field instanceof PDTerminalField)) {
            return name + "\t" + da + "\t\tnoterminal";
        }
        PDAnnotationWidget widget = null;
        for (PDAnnotationWidget w : ((PDTerminalField) field).getWidgets()) {
            widget = w;
            break;
        }
        if (widget == null) {
            return name + "\t" + da + "\t\tnowidget";
        }
        PDAppearanceDictionary ap = widget.getAppearance();
        if (ap == null) {
            return name + "\t" + da + "\t\tnoap";
        }
        PDAppearanceEntry normal = ap.getNormalAppearance();
        if (normal == null || !normal.isStream()) {
            return name + "\t" + da + "\t\tnoap";
        }
        PDAppearanceStream stream = normal.getAppearanceStream();

        List<String> ops = new ArrayList<>();
        List<COSBase> operands = new ArrayList<>();
        String tfFont = null;
        double tfSize = 0.0;
        boolean haveTf = false;
        String col = "none";
        int shows = 0;
        StringBuilder text = new StringBuilder();
        List<Long> baselines = new ArrayList<>();
        double penY = 0.0;

        PDFStreamParser parser =
                new PDFStreamParser(new PDAppearanceStream(stream.getCOSObject()));
        for (Object token = parser.parseNextToken();
                token != null;
                token = parser.parseNextToken()) {
            if (token instanceof Operator) {
                String op = ((Operator) token).getName();
                ops.add(op);
                if ("Tf".equals(op) && operands.size() >= 2) {
                    COSBase n = operands.get(operands.size() - 2);
                    if (n instanceof COSName) {
                        tfFont = ((COSName) n).getName();
                    }
                    tfSize = numOf(operands.get(operands.size() - 1));
                    haveTf = true;
                } else if ("g".equals(op) && operands.size() >= 1) {
                    col = "g:1";
                } else if ("rg".equals(op) && operands.size() >= 3) {
                    col = "rg:3";
                } else if ("k".equals(op) && operands.size() >= 4) {
                    col = "k:4";
                } else if ("cs".equals(op) && operands.size() >= 1) {
                    // PDFBox-3.0.7 routes the /DA non-stroking colour through a
                    // ``cs <space> sc`` pair instead of the literal g/rg/k
                    // operator. Project the named colour space so the test can
                    // map it back to the g/rg/k family pypdfbox emits.
                    COSBase cn = operands.get(operands.size() - 1);
                    if (cn instanceof COSName) {
                        String csName = ((COSName) cn).getName();
                        if ("DeviceGray".equals(csName)) {
                            col = "g:1";
                        } else if ("DeviceRGB".equals(csName)) {
                            col = "rg:3";
                        } else if ("DeviceCMYK".equals(csName)) {
                            col = "k:4";
                        } else {
                            col = "cs:" + csName;
                        }
                    }
                } else if (("Td".equals(op) || "TD".equals(op))
                        && operands.size() >= 2) {
                    penY += numOf(operands.get(operands.size() - 1));
                } else if ("Tm".equals(op) && operands.size() >= 6) {
                    penY = numOf(operands.get(5));
                } else if ("Tj".equals(op) || "'".equals(op) || "\"".equals(op)) {
                    shows++;
                    appendShown(text, operands);
                    recordBaseline(baselines, penY);
                } else if ("TJ".equals(op)) {
                    shows++;
                    appendTjArray(text, operands);
                    recordBaseline(baselines, penY);
                }
                operands.clear();
            } else if (token instanceof COSBase) {
                operands.add((COSBase) token);
            }
        }

        String facts = "tf=" + (haveTf ? tfFont + "/" + fmt(tfSize) : "none")
                + ";col=" + col
                + ";shows=" + shows
                + ";lines=" + Math.max(1, baselines.size())
                + ";text=" + text;
        return name + "\t" + da + "\t" + String.join(",", ops) + "\t" + facts;
    }

    private static void recordBaseline(List<Long> baselines, double penY) {
        long by = Math.round(penY);
        if (!baselines.contains(by)) {
            baselines.add(by);
        }
    }

    private static void appendShown(StringBuilder text, List<COSBase> operands) {
        if (operands.isEmpty()) {
            return;
        }
        COSBase last = operands.get(operands.size() - 1);
        if (last instanceof COSString) {
            text.append(sanitize(((COSString) last).getString()));
        }
    }

    private static void appendTjArray(StringBuilder text, List<COSBase> operands) {
        if (operands.isEmpty()) {
            return;
        }
        COSBase last = operands.get(operands.size() - 1);
        if (last instanceof COSArray) {
            for (COSBase el : (COSArray) last) {
                if (el instanceof COSString) {
                    text.append(sanitize(((COSString) el).getString()));
                }
            }
        }
    }

    private static String sanitize(String s) {
        return s.replace("\r\n", "|").replace("\n", "|").replace("\r", "|")
                .replace("\t", " ");
    }

    private static String resolveDa(PDField field) {
        try {
            java.lang.reflect.Method m =
                    field.getClass().getMethod("getDefaultAppearance");
            Object v = m.invoke(field);
            if (v instanceof String && !((String) v).isEmpty()) {
                return (String) v;
            }
        } catch (Exception ignored) {
            // not a variable-text field, or no /DA — fall through
        }
        return "none";
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
