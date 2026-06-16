import java.io.File;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.fdf.FDFAnnotation;
import org.apache.pdfbox.pdmodel.fdf.FDFDictionary;
import org.apache.pdfbox.pdmodel.fdf.FDFDocument;
import org.apache.pdfbox.pdmodel.fdf.FDFField;

/**
 * File-based malformed/edge fuzz for binary FDF documents loaded via
 * Loader.loadFDF. Complements FdfParserFuzzProbe (which fuzzes the on-wire
 * header / xref / trailer) by exercising the FDF *object model* instead:
 * value-type coercion of /V (string / name / array / stream), /Opt option
 * arrays, the qualified-field-name tree built from nested /Kids partial
 * names (/T), annotation count + subtype dispatch (incl. an unknown subtype),
 * a missing /FDF root sub-dictionary, and a self-referential (cyclic) kid.
 *
 * Each case is a raw ".fdf" byte file named in manifest.txt. For every case
 * the probe emits one canonical line:
 *
 *   CASE <name> OK fdf=<0|1> fields=<n> qnames=<a.b=v|...> annots=<n> types=<T|T>
 *
 * or "CASE <name> ERR" when Loader.loadFDF throws. "fields" is the count of
 * top-level /Fields entries (-1 when /Fields is absent), "qnames" is a
 * depth-first walk of every field's fully-qualified name (parent.T joined
 * with '.') and its getValue() repr, "annots" is the /Annots count (-1 when
 * absent) and "types" the simple class names of the dispatched annotations.
 */
public final class FdfFuzzProbe {
    private static String valueRepr(FDFField field) {
        Object value;
        try {
            value = field.getValue();
        } catch (Throwable error) {
            return "<err>";
        }
        if (value == null) {
            return "null";
        }
        if (value instanceof List<?> list) {
            List<String> parts = new ArrayList<>();
            for (Object item : list) {
                parts.add(String.valueOf(item));
            }
            return "[" + String.join("|", parts) + "]";
        }
        return String.valueOf(value);
    }

    private static void walkField(FDFField field, String prefix, List<String> out) {
        String partial = field.getPartialFieldName();
        String name = partial == null ? "" : partial;
        String qualified = prefix.isEmpty() ? name : prefix + "." + name;
        out.add(qualified + "=" + valueRepr(field));
        List<FDFField> kids = field.getKids();
        if (kids != null) {
            for (FDFField kid : kids) {
                // Guard against a self-referential cyclic kid: skip a kid that
                // is the same COS dictionary as its parent so the probe can't
                // recurse forever.
                if (kid.getCOSObject() == field.getCOSObject()) {
                    out.add(qualified + ".<cycle>");
                    continue;
                }
                walkField(kid, qualified, out);
            }
        }
    }

    private static String qnamesCell(List<FDFField> fields) {
        if (fields == null || fields.isEmpty()) {
            return "-";
        }
        List<String> out = new ArrayList<>();
        for (FDFField field : fields) {
            walkField(field, "", out);
        }
        return String.join("|", out);
    }

    private static String typesCell(List<FDFAnnotation> annots) {
        if (annots == null || annots.isEmpty()) {
            return "-";
        }
        List<String> out = new ArrayList<>();
        for (FDFAnnotation annot : annots) {
            out.add(annot == null ? "null" : annot.getClass().getSimpleName());
        }
        return String.join("|", out);
    }

    private static boolean fdfPresent(FDFDocument document) {
        COSBase root = document.getDocument().getTrailer()
                .getDictionaryObject(COSName.ROOT);
        if (!(root instanceof COSDictionary catalog)) {
            return false;
        }
        return catalog.getDictionaryObject(COSName.FDF) instanceof COSDictionary;
    }

    private static void emit(PrintStream out, File directory, String name) {
        try (FDFDocument document = Loader.loadFDF(new File(directory, name + ".fdf"))) {
            boolean present = fdfPresent(document);
            FDFDictionary fdf = document.getCatalog().getFDF();
            List<FDFField> fields = fdf.getFields();
            List<FDFAnnotation> annots = fdf.getAnnotations();
            out.println("CASE " + name + " OK fdf=" + (present ? 1 : 0)
                    + " fields=" + (fields == null ? -1 : fields.size())
                    + " qnames=" + qnamesCell(fields)
                    + " annots=" + (annots == null ? -1 : annots.size())
                    + " types=" + typesCell(annots));
        } catch (Throwable error) {
            out.println("CASE " + name + " ERR");
        }
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File directory = new File(args[0]);
        String manifest = Files.readString(
                new File(directory, "manifest.txt").toPath(), StandardCharsets.UTF_8);
        for (String raw : manifest.split("\\R")) {
            String name = raw.trim();
            if (!name.isEmpty()) {
                emit(out, directory, name);
            }
        }
    }
}
