import java.io.File;
import java.io.PrintStream;
import java.security.MessageDigest;
import java.util.Calendar;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDocumentNameDictionary;
import org.apache.pdfbox.pdmodel.common.PDNameTreeNode;
import org.apache.pdfbox.pdmodel.common.filespecification.PDComplexFileSpecification;
import org.apache.pdfbox.pdmodel.common.filespecification.PDEmbeddedFile;

/**
 * Live oracle probe: dump embedded-file *detail* + associated-file linkage.
 *
 * This is the file-spec / /Params surface that EmbedFilesProbe deliberately
 * does NOT cover. For every embedded file (flattened across the catalog's
 * /Names /EmbeddedFiles name tree, sorted by name) emit one canonical
 * tab-separated line carrying the rich file-spec + embedded-file fields:
 *
 *   ef \t name \t F \t UF \t AFRelationship \t subtype \t size \t
 *        created \t modified \t declen \t checksumHex \t contentSha1
 *
 * read via PDFBox's typed accessors (getFile / getFileUnicode /
 * getEmbeddedFile().getSize() / getCreationDate() / getModDate() /
 * getSubtype() / getCheckSum() / toByteArray()). The /AFRelationship name is
 * read raw from the file-spec COSDictionary because PDFBox 3.0.7 does not
 * surface a typed getAFRelationship() — that is canonical: the value pypdfbox
 * stores must equal the name byte-for-byte that PDFBox round-trips.
 *
 * Then the catalog-level /AF (associated files) array — also read raw from
 * COS for the same reason — emit one line per entry, in array order:
 *
 *   af \t index \t F \t UF \t AFRelationship
 *
 * Missing strings render as the literal "-"; an absent embedded stream
 * renders declen -1, checksumHex "-", contentSha1 "-"; an absent date NULL.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> EmbeddedFileDetailProbe input.pdf
 */
public final class EmbeddedFileDetailProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();

            // ---- /Names /EmbeddedFiles name tree, flattened + sorted. ----
            PDDocumentNameDictionary names = catalog.getNames();
            TreeMap<String, PDComplexFileSpecification> sorted = new TreeMap<>();
            if (names != null) {
                PDNameTreeNode<PDComplexFileSpecification> tree = names.getEmbeddedFiles();
                if (tree != null) {
                    collect(tree, sorted);
                }
            }
            for (Map.Entry<String, PDComplexFileSpecification> e : sorted.entrySet()) {
                out.println("ef\t" + e.getKey() + "\t" + specDetail(e.getValue()));
            }

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
            return "-\t-\t-\t-\t-1\tNULL\tNULL\t-1\t-\t-";
        }
        String f = nz(spec.getFile());
        String uf = nz(spec.getFileUnicode());
        String rel = rawName(spec.getCOSObject(), "AFRelationship");
        PDEmbeddedFile ef = spec.getEmbeddedFile();
        String subtype = "-";
        long size = -1;
        String created = "NULL";
        String modified = "NULL";
        long declen = -1;
        String checksum = "-";
        String contentSha = "-";
        if (ef != null) {
            subtype = nz(ef.getSubtype());
            size = ef.getSize();
            created = isoDate(ef.getCreationDate());
            modified = isoDate(ef.getModDate());
            byte[] data = ef.toByteArray();
            declen = data.length;
            contentSha = sha1(data);
            // CheckSum read raw from /Params as a COSString -> canonical hex,
            // binary-safe (the MD5 digest carries non-text bytes).
            checksum = checkSumHex(ef);
        }
        return f + "\t" + uf + "\t" + rel + "\t" + subtype + "\t" + size + "\t"
                + created + "\t" + modified + "\t" + declen + "\t" + checksum
                + "\t" + contentSha;
    }

    /** Hex of the raw /Params /CheckSum bytes, or "-" when absent/non-string. */
    private static String checkSumHex(PDEmbeddedFile ef) {
        COSBase params = ef.getCOSObject().getDictionaryObject(COSName.PARAMS);
        if (!(params instanceof COSDictionary)) {
            return "-";
        }
        COSBase cs = ((COSDictionary) params).getDictionaryObject(COSName.getPDFName("CheckSum"));
        if (!(cs instanceof COSString)) {
            return "-";
        }
        return hex(((COSString) cs).getBytes());
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

    private static String isoDate(Calendar c) {
        if (c == null) {
            return "NULL";
        }
        int offMillis = c.get(Calendar.ZONE_OFFSET) + c.get(Calendar.DST_OFFSET);
        int offMin = offMillis / 60000;
        char sign = offMin < 0 ? '-' : '+';
        int absMin = Math.abs(offMin);
        return String.format(
            "%04d-%02d-%02dT%02d:%02d:%02d%c%02d:%02d",
            c.get(Calendar.YEAR),
            c.get(Calendar.MONTH) + 1,
            c.get(Calendar.DAY_OF_MONTH),
            c.get(Calendar.HOUR_OF_DAY),
            c.get(Calendar.MINUTE),
            c.get(Calendar.SECOND),
            sign,
            absMin / 60,
            absMin % 60);
    }

    private static String nz(String s) {
        return s == null ? "-" : s;
    }

    private static String hex(byte[] data) {
        StringBuilder sb = new StringBuilder(data.length * 2);
        for (byte b : data) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }

    private static String sha1(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-1");
        return hex(md.digest(data));
    }
}
