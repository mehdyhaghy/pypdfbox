import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.common.filespecification.PDFileSpecification;
import org.apache.pdfbox.pdmodel.fdf.FDFAnnotation;
import org.apache.pdfbox.pdmodel.fdf.FDFDictionary;
import org.apache.pdfbox.pdmodel.fdf.FDFDocument;
import org.apache.pdfbox.pdmodel.fdf.FDFField;

/**
 * Live oracle probe for FDF / XFDF documents.
 *
 * Modes:
 *   dump      <kind> <input>                      load + emit canonical facts
 *   roundtrip <kind> <input> <outFdf> <outXfdf>   load, re-save FDF + XFDF,
 *                                                  then load each back and emit
 *                                                  the round-tripped facts.
 *
 * <kind> is "fdf" (Loader.loadFDF) or "xfdf" (Loader.loadXFDF).
 *
 * Canonical output lines (stable ordering, one fact per line, UTF-8):
 *   F=<source PDF path or - >
 *   FIELD <fully-qualified-name> | value=<repr> | kids=<n>
 *   ANNOT <subtype or -> | rect=<llx,lly,urx,ury or - >
 *
 * Fields are walked depth-first; the fully-qualified name joins partial names
 * with '.', matching how AcroForm addresses nested fields. The value repr is
 * "-" for null, the string for a scalar, or "[a|b|c]" for a list (multi-select).
 */
public final class FdfProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        String kind = args[1];
        String input = args[2];

        if ("dump".equals(mode)) {
            try (FDFDocument doc = load(kind, input)) {
                emit(doc, out);
            }
        } else if ("roundtrip".equals(mode)) {
            String outFdf = args[3];
            String outXfdf = args[4];
            try (FDFDocument doc = load(kind, input)) {
                doc.save(new File(outFdf));
                doc.saveXFDF(new File(outXfdf));
            }
            // Reload the re-saved FDF and emit its facts.
            try (FDFDocument reloaded = Loader.loadFDF(new File(outFdf))) {
                out.println("== fdf ==");
                emit(reloaded, out);
            }
            // Reload the re-saved XFDF and emit its facts.
            try (FDFDocument reloaded = Loader.loadXFDF(new File(outXfdf))) {
                out.println("== xfdf ==");
                emit(reloaded, out);
            }
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static FDFDocument load(String kind, String input) throws Exception {
        if ("xfdf".equals(kind)) {
            return Loader.loadXFDF(new File(input));
        }
        return Loader.loadFDF(new File(input));
    }

    private static void emit(FDFDocument doc, PrintStream out) throws Exception {
        FDFDictionary fdf = doc.getCatalog().getFDF();

        // /F source file.
        PDFileSpecification fs = fdf.getFile();
        String f = (fs == null || fs.getFile() == null) ? "-" : fs.getFile();
        out.println("F=" + f);

        // Fields (depth-first, fully-qualified names).
        List<FDFField> fields = fdf.getFields();
        if (fields != null) {
            for (FDFField field : fields) {
                emitField(field, "", out);
            }
        }

        // Annotations.
        List<FDFAnnotation> annots = fdf.getAnnotations();
        if (annots != null) {
            for (FDFAnnotation annot : annots) {
                String subtype = annot.getCOSObject().getNameAsString("Subtype");
                if (subtype == null) {
                    subtype = "-";
                }
                PDRectangle r = annot.getRectangle();
                String rect = (r == null) ? "-" : fmtRect(r);
                out.println("ANNOT " + subtype + " | rect=" + rect);
            }
        }
    }

    private static void emitField(FDFField field, String prefix, PrintStream out)
            throws Exception {
        String partial = field.getPartialFieldName();
        String fq = prefix.isEmpty()
                ? (partial == null ? "" : partial)
                : (partial == null ? prefix : prefix + "." + partial);

        Object value = field.getValue();
        String valueRepr = valueRepr(value);

        List<FDFField> kids = field.getKids();
        int kidCount = (kids == null) ? 0 : kids.size();

        out.println("FIELD " + fq + " | value=" + valueRepr + " | kids=" + kidCount);

        if (kids != null) {
            for (FDFField kid : kids) {
                emitField(kid, fq, out);
            }
        }
    }

    private static String valueRepr(Object value) {
        if (value == null) {
            return "-";
        }
        if (value instanceof List) {
            List<?> list = (List<?>) value;
            StringBuilder sb = new StringBuilder("[");
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) {
                    sb.append("|");
                }
                sb.append(String.valueOf(list.get(i)));
            }
            sb.append("]");
            return sb.toString();
        }
        return String.valueOf(value);
    }

    private static String fmtRect(PDRectangle r) {
        return fmt(r.getLowerLeftX()) + ","
                + fmt(r.getLowerLeftY()) + ","
                + fmt(r.getUpperRightX()) + ","
                + fmt(r.getUpperRightY());
    }

    private static String fmt(float v) {
        // Stable numeric formatting: trim a trailing ".0" so integral
        // coordinates compare equal across the two libraries.
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return String.valueOf((long) v);
        }
        return String.valueOf(v);
    }
}
