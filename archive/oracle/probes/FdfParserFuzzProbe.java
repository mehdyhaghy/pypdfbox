import java.io.File;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.fdf.FDFDictionary;
import org.apache.pdfbox.pdmodel.fdf.FDFDocument;
import org.apache.pdfbox.pdmodel.fdf.FDFField;

/** File-based malformed-input fuzz for Loader.loadFDF. */
public final class FdfParserFuzzProbe {
    private static void emit(PrintStream out, File directory, String name) {
        try (FDFDocument document = Loader.loadFDF(new File(directory, name + ".fdf"))) {
            FDFDictionary fdf = document.getCatalog().getFDF();
            List<FDFField> fields = fdf.getFields();
            out.println("CASE " + name + " OK version=" + document.getDocument().getVersion()
                    + " fields=" + (fields == null ? -1 : fields.size()));
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
