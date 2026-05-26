import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
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
 * Live oracle probe for AcroForm field SETTING + appearance generation.
 *
 * Two modes:
 *
 *   1. SET:  java FieldSetProbe set  in.pdf out.pdf  name=value [name=value ...]
 *            Loads in.pdf, calls field.setValue(value) on each named field
 *            (which in upstream PDFBox triggers appearance regeneration unless
 *            the AcroForm has NeedAppearances=true), saves to out.pdf.
 *
 *   2. READ: java FieldSetProbe read in.pdf  name [name ...]
 *            Loads in.pdf and emits, for each requested field (sorted by the
 *            requested order — but we sort for determinism), one LF-terminated
 *            line:
 *
 *              <fqName>\t<value>\t<hasN>\t<tokenCount>\t<opSequence>
 *
 *            where:
 *              - value       = getValueAsString(), escaped (newlines -> \\n)
 *              - hasN        = "1" when at least one widget carries /AP /N
 *                              (a stream or a state subdictionary), else "0"
 *              - tokenCount  = total decoded content-stream token count across
 *                              all widgets' /AP /N normal-appearance streams
 *                              ("0" when none)
 *              - opSequence  = the comma-joined sequence of *operator* tokens
 *                              (PDFBox Operator names) across those streams —
 *                              a structural fingerprint of the appearance
 *                              independent of exact coordinate values
 *
 * The READ mode is the differential surface: pypdfbox reloads the same saved
 * file and must report identical value, /AP /N presence, and a structurally
 * equivalent operator sequence.
 */
public final class FieldSetProbe {
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
            List<String> lines = new ArrayList<>();
            for (int i = 2; i < args.length; i++) {
                String name = args[i];
                PDField field = form.getField(name);
                if (field == null) {
                    lines.add(name + "\t<missing>\t0\t0\t");
                    continue;
                }
                lines.add(line(field));
            }
            Collections.sort(lines);
            StringBuilder sb = new StringBuilder();
            for (String l : lines) {
                sb.append(l).append('\n');
            }
            out.print(sb);
        }
    }

    private static String line(PDField field) throws Exception {
        String name = field.getFullyQualifiedName();
        String value = esc(field.getValueAsString());
        boolean hasN = false;
        int tokenCount = 0;
        List<String> ops = new ArrayList<>();
        if (field instanceof PDTerminalField) {
            for (PDAnnotationWidget widget : ((PDTerminalField) field).getWidgets()) {
                PDAppearanceDictionary ap = widget.getAppearance();
                if (ap == null) {
                    continue;
                }
                PDAppearanceEntry normal = ap.getNormalAppearance();
                if (normal == null) {
                    continue;
                }
                hasN = true;
                COSStream stream = null;
                if (normal.isStream()) {
                    stream = normal.getAppearanceStream().getCOSObject();
                } else {
                    // State subdictionary (check/radio): pick the entry matching
                    // the widget's /AS, falling back to any non-Off entry.
                    COSBase as = widget.getCOSObject().getDictionaryObject(COSName.AS);
                    PDAppearanceStream sel = pickState(normal, as);
                    if (sel != null) {
                        stream = sel.getCOSObject();
                    }
                }
                if (stream != null) {
                    int[] counts = tokenize(stream, ops);
                    tokenCount += counts[0];
                }
            }
        }
        return name + "\t" + value + "\t" + (hasN ? "1" : "0") + "\t"
                + tokenCount + "\t" + String.join(",", ops);
    }

    private static PDAppearanceStream pickState(PDAppearanceEntry normal, COSBase as) {
        java.util.Map<COSName, PDAppearanceStream> sub = normal.getSubDictionary();
        if (as instanceof COSName) {
            PDAppearanceStream hit = sub.get((COSName) as);
            if (hit != null) {
                return hit;
            }
        }
        for (java.util.Map.Entry<COSName, PDAppearanceStream> e : sub.entrySet()) {
            if (!COSName.OFF.equals(e.getKey())) {
                return e.getValue();
            }
        }
        return sub.isEmpty() ? null : sub.values().iterator().next();
    }

    /** Returns {tokenCount}; appends operator names to {@code ops}. */
    private static int[] tokenize(COSStream stream, List<String> ops) throws Exception {
        PDFStreamParser parser = new PDFStreamParser(
                new PDAppearanceStream(stream));
        int count = 0;
        for (Object token = parser.parseNextToken();
                token != null;
                token = parser.parseNextToken()) {
            count++;
            if (token instanceof org.apache.pdfbox.contentstream.operator.Operator) {
                ops.add(((org.apache.pdfbox.contentstream.operator.Operator) token).getName());
            }
        }
        return new int[] {count};
    }

    private static String esc(String s) {
        if (s == null) {
            return "none";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
