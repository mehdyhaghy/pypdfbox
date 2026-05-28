import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
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
import org.apache.pdfbox.pdmodel.interactive.form.PDChoice;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDListBox;

/**
 * Live oracle probe for AcroForm LIST-BOX appearance generation.
 *
 * Mirrors the surface pypdfbox's PDAppearanceGenerator._generate_choice /
 * _regenerate_listbox_widget exercises when PDListBox.setValue regenerates the
 * widget /AP /N stream: upstream's insertGeneratedListboxAppearance draws every
 * option row one-per-line starting at the /TI scroll offset, paints a flat
 * highlight fill rectangle behind each selected row, then shows the row labels.
 *
 * Two modes:
 *
 *   1. SET:  java ListBoxApProbe set in.pdf out.pdf name=v|v|... [name=...]
 *            Loads a pypdfbox-built form, calls PDChoice.setValue on each named
 *            field (multi value when it contains '|'), so upstream PDFBox
 *            composes its own appearance into the same field configuration, then
 *            saves out.pdf. Forces an apples-to-apples READ comparison.
 *
 *   2. READ: java ListBoxApProbe read in.pdf name [name ...]
 *            Loads in.pdf and emits, per field, one LF-terminated tab-separated
 *            record:
 *
 *              fqName \t bboxW \t bboxH \t opSeq \t facts
 *
 *            where:
 *              - bboxW / bboxH = /AP /N /BBox size, rounded to int
 *              - opSeq = comma-joined operator-name sequence (structural
 *                        fingerprint)
 *              - facts = semicolon-joined key tokens:
 *                          tf=<fontResName>/<size>  the Tf font + size
 *                          rows=<n>  number of show-text rows (one Tj per option)
 *                          fills=<n> number of fill (f/F) ops — selection
 *                                    highlight rectangles
 *                          tj=<text> one per shown option label (in order)
 */
public final class ListBoxApProbe {

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
                if (field instanceof PDChoice) {
                    PDChoice ch = (PDChoice) field;
                    if (value.indexOf('|') >= 0) {
                        List<String> vals = new ArrayList<>();
                        for (String v : value.split("\\|", -1)) {
                            vals.add(v);
                        }
                        ch.setValue(vals);
                    } else {
                        ch.setValue(value);
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
                    sb.append(name).append("\t<missing>\t0\t0\t\t\n");
                    continue;
                }
                sb.append(line(field)).append('\n');
            }
            out.print(sb);
        }
    }

    private static String line(PDField field) throws Exception {
        String name = field.getFullyQualifiedName();
        int bboxW = 0;
        int bboxH = 0;
        List<String> ops = new ArrayList<>();
        List<String> facts = new ArrayList<>();

        if (field instanceof PDListBox) {
            for (PDAnnotationWidget widget : ((PDListBox) field).getWidgets()) {
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
                walk(stream.getCOSObject(), ops, facts);
                // First widget only — identical appearance across kids.
                break;
            }
        }
        return name + "\t" + bboxW + "\t" + bboxH + "\t"
                + String.join(",", ops) + "\t" + String.join(";", facts);
    }

    /**
     * Tokenise the appearance content stream, appending operator names to
     * {@code ops} and key text/structure tokens to {@code facts}: the Tf font +
     * size, the show-text row count + each row's literal, and the number of
     * path-fill operations (the selection highlight rectangles).
     */
    private static void walk(COSStream stream, List<String> ops, List<String> facts)
            throws Exception {
        PDFStreamParser parser = new PDFStreamParser(new PDAppearanceStream(stream));
        List<COSBase> operands = new ArrayList<>();
        int rows = 0;
        int fills = 0;
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
                } else if ("f".equals(op) || "F".equals(op) || "f*".equals(op)) {
                    fills++;
                } else if ("Tj".equals(op) || "'".equals(op) || "\"".equals(op)) {
                    if (!operands.isEmpty()) {
                        COSBase last = operands.get(operands.size() - 1);
                        if (last instanceof COSString) {
                            facts.add("tj=" + esc(((COSString) last).getString()));
                        }
                    }
                    rows++;
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
                    rows++;
                }
                operands.clear();
            } else if (token instanceof COSBase) {
                operands.add((COSBase) token);
            }
        }
        facts.add("rows=" + rows);
        facts.add("fills=" + fills);
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
        return String.format(java.util.Locale.ROOT, "%.2f", d);
    }

    private static String esc(String s) {
        if (s == null) {
            return "none";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t").replace(";", "\\u003b").replace(",", "\\u002c");
    }
}
