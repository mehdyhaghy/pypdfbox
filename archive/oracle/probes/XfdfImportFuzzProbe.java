import java.io.File;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.pdmodel.common.filespecification.PDFileSpecification;
import org.apache.pdfbox.pdmodel.fdf.FDFAnnotation;
import org.apache.pdfbox.pdmodel.fdf.FDFDictionary;
import org.apache.pdfbox.pdmodel.fdf.FDFDocument;
import org.apache.pdfbox.pdmodel.fdf.FDFField;

/** File-based malformed-input fuzz for Loader.loadXFDF. */
public final class XfdfImportFuzzProbe {
    private static String fieldCell(FDFField field) throws Exception {
        Object value = field.getValue();
        List<FDFField> kids = field.getKids();
        return String.valueOf(field.getPartialFieldName()) + "=" + String.valueOf(value)
                + "/" + (kids == null ? 0 : kids.size());
    }

    private static String fieldsCell(List<FDFField> fields) throws Exception {
        if (fields == null || fields.isEmpty()) {
            return "-";
        }
        List<String> values = new ArrayList<>();
        for (FDFField field : fields) {
            values.add(fieldCell(field));
            List<FDFField> kids = field.getKids();
            if (kids != null) {
                for (FDFField kid : kids) {
                    values.add(">" + fieldCell(kid));
                }
            }
        }
        return String.join("|", values);
    }

    private static String annotationsCell(List<FDFAnnotation> annotations) {
        if (annotations == null || annotations.isEmpty()) {
            return "-";
        }
        List<String> values = new ArrayList<>();
        for (FDFAnnotation annotation : annotations) {
            values.add(annotation == null ? "null" : annotation.getClass().getSimpleName());
        }
        return String.join("|", values);
    }

    private static void emit(PrintStream out, File directory, String name) {
        try (FDFDocument document = Loader.loadXFDF(new File(directory, name + ".xfdf"))) {
            FDFDictionary fdf = document.getCatalog().getFDF();
            PDFileSpecification file = fdf.getFile();
            COSArray ids = fdf.getID();
            out.println("CASE " + name + " OK fields=" + fieldsCell(fdf.getFields())
                    + " annots=" + annotationsCell(fdf.getAnnotations())
                    + " file=" + (file == null ? "null" : String.valueOf(file.getFile()))
                    + " ids=" + (ids == null ? 0 : ids.size()));
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
