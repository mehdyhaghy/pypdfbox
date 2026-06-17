import java.io.File;
import java.io.PrintStream;
import java.security.MessageDigest;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDocumentNameDictionary;
import org.apache.pdfbox.pdmodel.common.PDNameTreeNode;
import org.apache.pdfbox.pdmodel.common.filespecification.PDComplexFileSpecification;
import org.apache.pdfbox.pdmodel.common.filespecification.PDEmbeddedFile;

/**
 * Live oracle probe: dump the catalog's /Names /EmbeddedFiles name tree.
 *
 * For every embedded file (flattened across the name-tree, sorted by name)
 * emit one canonical TSV line:
 *   name \t F-filename \t UF-filename \t byte-length \t sha1(decoded-bytes)
 * Missing /F or /UF render as the literal "-"; an absent embedded stream
 * renders length -1 and sha1 "-".
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> EmbedFilesProbe input.pdf
 */
public final class EmbedFilesProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDDocumentNameDictionary names = catalog.getNames();
            // Flatten the name tree into a sorted (by name) map.
            TreeMap<String, PDComplexFileSpecification> sorted = new TreeMap<>();
            if (names != null) {
                PDNameTreeNode<PDComplexFileSpecification> tree = names.getEmbeddedFiles();
                if (tree != null) {
                    collect(tree, sorted);
                }
            }
            for (Map.Entry<String, PDComplexFileSpecification> e : sorted.entrySet()) {
                String name = e.getKey();
                PDComplexFileSpecification spec = e.getValue();
                String f = nz(spec == null ? null : spec.getFile());
                String uf = nz(spec == null ? null : spec.getFileUnicode());
                PDEmbeddedFile ef = spec == null ? null : spec.getEmbeddedFile();
                long length = -1;
                String sha = "-";
                if (ef != null) {
                    byte[] data = ef.toByteArray();
                    length = data.length;
                    sha = sha1(data);
                }
                out.println(name + "\t" + f + "\t" + uf + "\t" + length + "\t" + sha);
            }
        }
    }

    private static void collect(
            PDNameTreeNode<PDComplexFileSpecification> node,
            TreeMap<String, PDComplexFileSpecification> sink) throws Exception {
        Map<String, PDComplexFileSpecification> leaf = node.getNames();
        if (leaf != null) {
            sink.putAll(leaf);
        }
        java.util.List<PDNameTreeNode<PDComplexFileSpecification>> kids = node.getKids();
        if (kids != null) {
            for (PDNameTreeNode<PDComplexFileSpecification> kid : kids) {
                collect(kid, sink);
            }
        }
    }

    private static String nz(String s) {
        return s == null ? "-" : s;
    }

    private static String sha1(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-1");
        byte[] digest = md.digest(data);
        StringBuilder sb = new StringBuilder(digest.length * 2);
        for (byte b : digest) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }
}
