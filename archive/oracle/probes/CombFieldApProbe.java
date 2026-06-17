import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
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
 * Live oracle probe for COMB text-field appearance generation —
 * AppearanceGeneratorHelper.insertGeneratedCombAppearance.
 *
 * A comb text field carries the Comb /Ff flag (bit 25) plus /MaxLen N. On
 * setValue, PDFBox lays the value's characters into N evenly-spaced cells
 * across the field width, each glyph centred in its cell via an incremental
 * per-cell ``newLineAtOffset`` (Td) scheme with an ascent-centred baseline.
 *
 * Two modes:
 *
 *   1. SET:  java CombFieldApProbe set in.pdf out.pdf name=value [...]
 *            Loads a pypdfbox-built form, calls setValue on each named field
 *            (PDFBox regenerates the comb appearance), saves to out.pdf.
 *
 *   2. READ: java CombFieldApProbe read in.pdf name [name ...]
 *            Emits one JSON object per requested field on its own line:
 *
 *              {"name":..,"maxLen":N,"bboxW":..,"bboxH":..,
 *               "combWidth":..,"cells":M,
 *               "tds":[[dx,dy],...],"text":".."}
 *
 *            tds = the per-cell newLineAtOffset (Td) operands in stream order,
 *            rounded to 3 decimals. combWidth = bboxW / maxLen. The Td deltas
 *            ARE the comb geometry the parity test asserts on.
 */
public final class CombFieldApProbe {

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
                sb.append(json(field, name)).append('\n');
            }
            out.print(sb);
        }
    }

    private static String json(PDField field, String name) throws Exception {
        int maxLen = -1;
        if (field != null && field.getCOSObject()
                .getDictionaryObject(org.apache.pdfbox.cos.COSName.getPDFName("MaxLen")) != null) {
            maxLen = field.getCOSObject().getInt("MaxLen");
        }
        double bboxW = 0;
        double bboxH = 0;
        List<double[]> tds = new ArrayList<>();
        StringBuilder text = new StringBuilder();

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
                    bboxW = stream.getBBox().getWidth();
                    bboxH = stream.getBBox().getHeight();
                }
                walk(stream.getCOSObject(), tds, text);
                break;
            }
        }

        double combWidth = (maxLen > 0) ? bboxW / maxLen : 0.0;

        StringBuilder sb = new StringBuilder();
        sb.append('{');
        sb.append("\"name\":\"").append(esc(name)).append("\",");
        sb.append("\"maxLen\":").append(maxLen).append(',');
        sb.append("\"bboxW\":").append(fmt(bboxW)).append(',');
        sb.append("\"bboxH\":").append(fmt(bboxH)).append(',');
        sb.append("\"combWidth\":").append(fmt(combWidth)).append(',');
        sb.append("\"cells\":").append(tds.size()).append(',');
        sb.append("\"tds\":[");
        for (int i = 0; i < tds.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append('[').append(fmt(tds.get(i)[0])).append(',')
                    .append(fmt(tds.get(i)[1])).append(']');
        }
        sb.append("],");
        sb.append("\"text\":\"").append(esc(text.toString())).append('"');
        sb.append('}');
        return sb.toString();
    }

    /**
     * Tokenise the appearance content stream; record each newLineAtOffset
     * (Td) operand pair, and the concatenated show-text.
     */
    private static void walk(COSStream stream, List<double[]> tds, StringBuilder text)
            throws Exception {
        PDFStreamParser parser = new PDFStreamParser(new PDAppearanceStream(stream));
        List<COSBase> operands = new ArrayList<>();
        for (Object token = parser.parseNextToken();
                token != null;
                token = parser.parseNextToken()) {
            if (token instanceof Operator) {
                String op = ((Operator) token).getName();
                if (("Td".equals(op) || "TD".equals(op)) && operands.size() >= 2) {
                    double dx = numOf(operands.get(operands.size() - 2));
                    double dy = numOf(operands.get(operands.size() - 1));
                    tds.add(new double[] {dx, dy});
                } else if ("Tj".equals(op) && !operands.isEmpty()) {
                    COSBase last = operands.get(operands.size() - 1);
                    if (last instanceof COSString) {
                        text.append(((COSString) last).getString());
                    }
                }
                operands.clear();
            } else if (token instanceof COSBase) {
                operands.add((COSBase) token);
            }
        }
    }

    private static double numOf(COSBase b) {
        if (b instanceof COSNumber) {
            return ((COSNumber) b).floatValue();
        }
        return 0.0;
    }

    private static String fmt(double d) {
        return String.format(Locale.ROOT, "%.3f", d);
    }

    private static String esc(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t");
    }
}
