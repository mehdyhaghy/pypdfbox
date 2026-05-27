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
 * Live oracle probe for AcroForm TEXT-FIELD appearance generation.
 *
 * Mirrors the surface pypdfbox's AppearanceGeneratorHelper / PDAppearanceGenerator
 * exercises when PDTextField.setValue regenerates the widget /AP /N stream:
 * the /DA font + size, /Q quadding (0 left / 1 centre / 2 right), the multiline
 * Ff flag (auto line-wrap), comb fields (/MaxLen + comb flag → evenly spaced
 * cells), and auto-font-size (size 0 → fit).
 *
 * Two modes:
 *
 *   1. SET:  java TextFieldApProbe set in.pdf out.pdf name=value [name=value ...]
 *            Loads a pypdfbox-built form, calls field.setValue(value) on each
 *            named field (upstream PDFBox regenerates the appearance), saves
 *            to out.pdf. This forces PDFBox's own AppearanceGeneratorHelper to
 *            compose the appearance into the same field configuration pypdfbox
 *            produced, so the READ-mode comparison is apples-to-apples.
 *
 *   2. READ: java TextFieldApProbe read in.pdf name [name ...]
 *            Loads in.pdf and emits, for each requested field, one
 *            LF-terminated tab-separated record:
 *
 *              fqName \t da \t bboxW \t bboxH \t opSeq \t facts
 *
 *            where:
 *              - da     = the resolved /DA string (field, falling back to the
 *                         AcroForm), or "none"
 *              - bboxW  = the /AP /N /BBox width, rounded to int
 *              - bboxH  = the /AP /N /BBox height, rounded to int
 *              - opSeq  = comma-joined operator-name sequence across the
 *                         widget's normal-appearance content stream — the
 *                         structural fingerprint
 *              - facts  = semicolon-joined key tokens, each as key=value:
 *                           tf=<fontResName>/<size>   (the Tf font + size)
 *                           tx=<x>   one per Td / Tm horizontal offset, the
 *                                    running absolute x rounded to int
 *                           bucket=<L|C|R>  alignment bucket derived from the
 *                                    first show-text x relative to BBox width
 *                           tj=<text>  one per shown string (Tj / TJ literal)
 *                           cells=<n>  number of show-text operations
 */
public final class TextFieldApProbe {

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
                    sb.append(name).append("\t<missing>\t0\t0\t\t\n");
                    continue;
                }
                sb.append(line(field, form)).append('\n');
            }
            out.print(sb);
        }
    }

    private static String line(PDField field, PDAcroForm form) throws Exception {
        String name = field.getFullyQualifiedName();
        String da = resolveDA(field, form);
        int bboxW = 0;
        int bboxH = 0;
        List<String> ops = new ArrayList<>();
        List<String> facts = new ArrayList<>();

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
                if (stream.getBBox() != null) {
                    bboxW = Math.round(stream.getBBox().getWidth());
                    bboxH = Math.round(stream.getBBox().getHeight());
                }
                walk(stream.getCOSObject(), ops, facts, bboxW);
                // First widget only — the reported facts describe the value
                // appearance which is identical across widget kids.
                break;
            }
        }
        return name + "\t" + esc(da) + "\t" + bboxW + "\t" + bboxH + "\t"
                + String.join(",", ops) + "\t" + String.join(";", facts);
    }

    /** Resolve the field /DA, falling back to the AcroForm /DA. */
    private static String resolveDA(PDField field, PDAcroForm form) {
        COSBase da = field.getCOSObject().getDictionaryObject(COSName.DA);
        if (da instanceof COSString) {
            return ((COSString) da).getString();
        }
        if (form != null) {
            String fda = form.getDefaultAppearance();
            if (fda != null && !fda.isEmpty()) {
                return fda;
            }
        }
        return "none";
    }

    /**
     * Tokenise the appearance content stream, appending operator names to
     * {@code ops} and key text tokens to {@code facts}.
     *
     * Tracks Td / TD / Tm horizontal translation to derive the running
     * absolute x of each text-show, the Tf font + size, and a left/centre/
     * right alignment bucket from the first show-text x relative to the
     * BBox width.
     */
    private static void walk(COSStream stream, List<String> ops, List<String> facts,
            int bboxW) throws Exception {
        PDFStreamParser parser = new PDFStreamParser(new PDAppearanceStream(stream));
        List<COSBase> operands = new ArrayList<>();
        double penX = 0.0;
        double penY = 0.0;
        int cells = 0;
        boolean firstShown = true;
        double firstShownX = 0.0;
        // Distinct baselines on which text was shown — the line count.
        List<Long> baselines = new ArrayList<>();
        for (Object token = parser.parseNextToken();
                token != null;
                token = parser.parseNextToken()) {
            if (token instanceof Operator) {
                String op = ((Operator) token).getName();
                ops.add(op);
                if ("Tf".equals(op) && operands.size() >= 2) {
                    String fontName = nameOf(operands.get(operands.size() - 2));
                    double size = numOf(operands.get(operands.size() - 1));
                    facts.add("tf=" + fontName + "/" + fmt(size));
                } else if ("Td".equals(op) || "TD".equals(op)) {
                    if (operands.size() >= 2) {
                        penX += numOf(operands.get(operands.size() - 2));
                        penY += numOf(operands.get(operands.size() - 1));
                        facts.add("tx=" + Math.round(penX));
                    }
                } else if ("Tm".equals(op)) {
                    if (operands.size() >= 6) {
                        // Tm operands are (a b c d e f); e (index 4) is the x
                        // translation, f (index 5) the y. Tm sets the matrix
                        // absolutely.
                        penX = numOf(operands.get(4));
                        penY = numOf(operands.get(5));
                        facts.add("tx=" + Math.round(penX));
                    }
                } else if ("T*".equals(op)) {
                    // Move to next line — advances y by the leading (TL).
                    // We can't read TL cheaply here; record a fresh baseline
                    // by nudging penY so the rounded value differs.
                    penY -= 1.0;
                } else if ("Tj".equals(op) || "'".equals(op) || "\"".equals(op)) {
                    if (!operands.isEmpty()) {
                        COSBase last = operands.get(operands.size() - 1);
                        if (last instanceof COSString) {
                            facts.add("tj=" + esc(((COSString) last).getString()));
                        }
                    }
                    cells++;
                    long by = Math.round(penY);
                    if (!baselines.contains(by)) {
                        baselines.add(by);
                    }
                    if (firstShown) {
                        firstShown = false;
                        firstShownX = penX;
                    }
                } else if ("TJ".equals(op)) {
                    if (!operands.isEmpty()
                            && operands.get(operands.size() - 1) instanceof COSArray) {
                        COSArray arr = (COSArray) operands.get(operands.size() - 1);
                        StringBuilder text = new StringBuilder();
                        for (COSBase el : arr) {
                            if (el instanceof COSString) {
                                text.append(((COSString) el).getString());
                            }
                        }
                        facts.add("tj=" + esc(text.toString()));
                    }
                    cells++;
                    long by = Math.round(penY);
                    if (!baselines.contains(by)) {
                        baselines.add(by);
                    }
                    if (firstShown) {
                        firstShown = false;
                        firstShownX = penX;
                    }
                }
                operands.clear();
            } else if (token instanceof COSBase) {
                operands.add((COSBase) token);
            }
        }
        facts.add("cells=" + cells);
        facts.add("lines=" + Math.max(1, baselines.size()));
        facts.add("bucket=" + bucket(firstShownX, bboxW));
    }

    /**
     * Derive a left / centre / right alignment bucket from the first
     * show-text x relative to the BBox width. Near 0 → L, near the middle
     * → C, near the right → R. Thresholds use the BBox width thirds.
     */
    private static String bucket(double x, int bboxW) {
        if (bboxW <= 0) {
            return "L";
        }
        double third = bboxW / 3.0;
        if (x < third) {
            return "L";
        }
        if (x < 2.0 * third) {
            return "C";
        }
        return "R";
    }

    private static String nameOf(COSBase b) {
        if (b instanceof COSName) {
            return ((COSName) b).getName();
        }
        return "?";
    }

    private static double numOf(COSBase b) {
        if (b instanceof COSNumber) {
            return ((COSNumber) b).floatValue();
        }
        return 0.0;
    }

    private static String fmt(double d) {
        if (d == Math.rint(d)) {
            return Long.toString((long) d);
        }
        return String.format(Locale.ROOT, "%.2f", d);
    }

    private static String esc(String s) {
        if (s == null) {
            return "none";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t").replace(";", "\\u003b").replace(",", "\\u002c");
    }
}
