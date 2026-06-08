import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.IdentityHashMap;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Differential fuzz probe for lazy indirect-reference and object-pool cycle
 * resolution in PDFBox 3.0.7. Wave 1520, agent A.
 *
 * <p>Each manifest entry names a tiny PDF whose object {@code 1 0 R} contains
 * a scalar, a direct or indirect cycle, a missing target, or a generation
 * mismatch. The projection walks raw array/dictionary entries and
 * {@code COSObject.getObject()} targets with identity markers, so malformed
 * cycles terminate without hiding whether the pool reused the same holder.
 */
public final class IndirectReferenceCycleFuzzProbe {

    private static PrintStream out;

    private static String walk(
            COSBase base, IdentityHashMap<COSBase, Integer> seen) {
        if (base == null || base instanceof COSNull) {
            return "null";
        }
        Integer prior = seen.get(base);
        if (prior != null) {
            return "@" + prior;
        }
        seen.put(base, seen.size());

        if (base instanceof COSObject) {
            COSObject object = (COSObject) base;
            return "ref(" + object.getObjectNumber() + ":"
                    + object.getGenerationNumber() + ")->"
                    + walk(object.getObject(), seen);
        }
        if (base instanceof COSInteger) {
            return "int(" + ((COSInteger) base).longValue() + ")";
        }
        if (base instanceof COSArray) {
            COSArray array = (COSArray) base;
            List<String> values = new ArrayList<>();
            for (int i = 0; i < array.size(); i++) {
                values.add(walk(array.get(i), seen));
            }
            return "array[" + String.join(",", values) + "]";
        }
        if (base instanceof COSDictionary) {
            COSDictionary dictionary = (COSDictionary) base;
            List<COSName> keys = new ArrayList<>(dictionary.keySet());
            keys.sort(Comparator.comparing(COSName::getName));
            List<String> values = new ArrayList<>();
            for (COSName key : keys) {
                values.add("/" + key.getName() + "->"
                        + walk(dictionary.getItem(key), seen));
            }
            return "dict{" + String.join(",", values) + "}";
        }
        return "other(" + base.getClass().getSimpleName() + ")";
    }

    private static String project(File pdf) {
        PDDocument document = null;
        try {
            document = Loader.loadPDF(pdf);
            COSObject target = document.getDocument().getObjectFromPool(
                    new COSObjectKey(1, 0));
            return walk(target, new IdentityHashMap<>());
        } catch (Throwable throwable) {
            return "ERR:" + throwable.getClass().getSimpleName();
        } finally {
            if (document != null) {
                try {
                    document.close();
                } catch (Exception ignored) {
                    // best-effort close
                }
            }
        }
    }

    private static void runCase(File directory, String name) {
        out.println("CASE " + name + " "
                + project(new File(directory, name + ".pdf")));
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File directory = new File(args[0]);
        File manifest = new File(directory, "manifest.txt");
        String[] names = new String(
                java.nio.file.Files.readAllBytes(manifest.toPath()),
                java.nio.charset.StandardCharsets.UTF_8).split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(name -> !name.isEmpty())
                .forEach(name -> runCase(directory, name));
    }
}
