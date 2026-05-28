import java.io.File;
import java.io.PrintStream;
import java.security.MessageDigest;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDocumentNameDictionary;
import org.apache.pdfbox.pdmodel.common.PDNameTreeNode;
import org.apache.pdfbox.pdmodel.common.filespecification.PDComplexFileSpecification;
import org.apache.pdfbox.pdmodel.common.filespecification.PDEmbeddedFile;

/**
 * Live oracle probe for the *multi-attachment* embedded-files surface that
 * EmbedFilesProbe + EmbeddedFileDetailProbe (single rich attachment) don't
 * exercise.
 *
 * For every embedded file flattened across the catalog's
 * /Names /EmbeddedFiles name tree, sorted by name, emit::
 *
 *   ef \t name \t F \t UF \t Desc \t AFRelationship \t hasEFF \t hasEFUF \t
 *        declenF \t shaF \t declenUF \t shaUF
 *
 * - "hasEFF" / "hasEFUF" — "Y" or "N", whether /EF/F and /EF/UF resolve to
 *   embedded streams (the dual-slot case PDFBox lets producers write).
 * - "declenF" / "shaF" — decoded byte length + SHA-1 of /EF/F (or -1 / "-").
 * - "declenUF" / "shaUF" — same for /EF/UF.
 * - "Desc" comes from getFileDescription(); missing renders "-".
 *
 * Then a "tree" line capturing the structural shape of the name tree::
 *
 *   tree \t leafCount \t kidCount \t totalNames
 *
 * - "leafCount" — number of nodes that carry a /Names array (leaves).
 * - "kidCount"  — number of nodes that carry a /Kids array (internal).
 * - "totalNames" — total embedded files reachable from the root.
 *
 * Finally, for the catalog-level /AF (associated files) array, emit::
 *
 *   af \t index \t F \t UF \t AFRelationship
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> EmbeddedFilesMultiProbe input.pdf
 */
public final class EmbeddedFilesMultiProbe {

    private static int leafCount = 0;
    private static int kidCount = 0;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();

            // ---- /Names /EmbeddedFiles name tree, flattened + sorted. ----
            PDDocumentNameDictionary names = catalog.getNames();
            TreeMap<String, PDComplexFileSpecification> sorted = new TreeMap<>();
            PDNameTreeNode<PDComplexFileSpecification> root = null;
            if (names != null) {
                root = names.getEmbeddedFiles();
                if (root != null) {
                    collect(root, sorted);
                }
            }
            for (Map.Entry<String, PDComplexFileSpecification> e : sorted.entrySet()) {
                out.println("ef\t" + e.getKey() + "\t" + specDetail(e.getValue()));
            }

            // ---- Tree shape ----
            leafCount = 0;
            kidCount = 0;
            int totalNames = sorted.size();
            if (root != null) {
                walkShape(root);
            }
            out.println("tree\t" + leafCount + "\t" + kidCount + "\t" + totalNames);

            // ---- catalog /AF associated files, raw COS, array order. ----
            COSDictionary cat = catalog.getCOSObject();
            COSBase afBase = cat.getDictionaryObject(COSName.getPDFName("AF"));
            if (afBase instanceof COSArray) {
                COSArray af = (COSArray) afBase;
                for (int i = 0; i < af.size(); i++) {
                    COSBase entry = af.getObject(i);
                    String f = "-";
                    String uf = "-";
                    String rel = "-";
                    if (entry instanceof COSDictionary) {
                        COSDictionary fs = (COSDictionary) entry;
                        f = nz(fs.getString(COSName.F));
                        uf = nz(fs.getString(COSName.UF));
                        rel = rawName(fs, "AFRelationship");
                    }
                    out.println("af\t" + i + "\t" + f + "\t" + uf + "\t" + rel);
                }
            }
        }
    }

    /** Emit the rich file-spec + embedded-file fields for one spec. */
    private static String specDetail(PDComplexFileSpecification spec) throws Exception {
        if (spec == null) {
            return "-\t-\t-\t-\tN\tN\t-1\t-\t-1\t-";
        }
        String f = nz(spec.getFile());
        String uf = nz(spec.getFileUnicode());
        String desc = nz(spec.getFileDescription());
        String rel = rawName(spec.getCOSObject(), "AFRelationship");

        // Probe each /EF slot independently — raw COS so we don't fall back
        // from /F to /UF (the typed getEmbeddedFile() does that).
        COSDictionary fsDict = spec.getCOSObject();
        COSBase efBase = fsDict.getDictionaryObject(COSName.EF);
        boolean hasF = false;
        boolean hasUF = false;
        long declenF = -1;
        long declenUF = -1;
        String shaF = "-";
        String shaUF = "-";
        if (efBase instanceof COSDictionary) {
            COSDictionary efDict = (COSDictionary) efBase;
            hasF = efDict.getDictionaryObject(COSName.F) != null;
            hasUF = efDict.getDictionaryObject(COSName.UF) != null;
        }
        // For decoded bytes use the typed accessor (it triggers the filter
        // chain). /F slot:
        if (hasF) {
            PDEmbeddedFile efF = spec.getEmbeddedFile();
            if (efF != null) {
                byte[] data = efF.toByteArray();
                declenF = data.length;
                shaF = sha1(data);
            }
        }
        if (hasUF) {
            PDEmbeddedFile efUF = spec.getEmbeddedFileUnicode();
            if (efUF != null) {
                byte[] data = efUF.toByteArray();
                declenUF = data.length;
                shaUF = sha1(data);
            }
        }
        return f + "\t" + uf + "\t" + desc + "\t" + rel + "\t"
                + (hasF ? "Y" : "N") + "\t" + (hasUF ? "Y" : "N") + "\t"
                + declenF + "\t" + shaF + "\t" + declenUF + "\t" + shaUF;
    }

    /** Read a name-valued entry as its raw string, "-" when absent/non-name. */
    private static String rawName(COSDictionary dict, String key) {
        if (dict == null) {
            return "-";
        }
        COSBase v = dict.getDictionaryObject(COSName.getPDFName(key));
        if (v instanceof COSName) {
            return ((COSName) v).getName();
        }
        return "-";
    }

    private static void collect(
            PDNameTreeNode<PDComplexFileSpecification> node,
            TreeMap<String, PDComplexFileSpecification> sink) throws Exception {
        Map<String, PDComplexFileSpecification> leaf = node.getNames();
        if (leaf != null) {
            sink.putAll(leaf);
        }
        List<PDNameTreeNode<PDComplexFileSpecification>> kids = node.getKids();
        if (kids != null) {
            for (PDNameTreeNode<PDComplexFileSpecification> kid : kids) {
                collect(kid, sink);
            }
        }
    }

    /** Walk the tree counting leaves (have /Names) and internals (have /Kids). */
    private static void walkShape(PDNameTreeNode<PDComplexFileSpecification> node) {
        COSDictionary dict = node.getCOSObject();
        if (dict.getDictionaryObject(COSName.NAMES) instanceof COSArray) {
            leafCount++;
        }
        COSBase kidsBase = dict.getDictionaryObject(COSName.KIDS);
        if (kidsBase instanceof COSArray) {
            kidCount++;
        }
        // Recurse via PDFBox's typed kids list.
        List<PDNameTreeNode<PDComplexFileSpecification>> kids = node.getKids();
        if (kids != null) {
            for (PDNameTreeNode<PDComplexFileSpecification> kid : kids) {
                walkShape(kid);
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
