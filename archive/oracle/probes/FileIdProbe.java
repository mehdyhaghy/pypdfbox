import java.io.File;
import java.io.FileOutputStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;

/**
 * Live oracle probe for the trailer /ID file identifier.
 *
 * Modes (args[0]):
 *
 *   read  in.pdf
 *       Load in.pdf and emit its trailer /ID facts (no re-save).
 *
 *   save  in.pdf out.pdf
 *       Full-save in.pdf to out.pdf via PDFBox, reload out.pdf, emit the
 *       /ID it wrote.
 *
 *   incremental  in.pdf out.pdf
 *       Capture the source /ID, mutate the catalog (dirty), incremental-save
 *       to out.pdf, reload, and emit before/after /ID facts so a parity test
 *       can verify /ID[0] is preserved and /ID[1] is updated.
 *
 * Output is line-oriented ``key=value``; a parity test parses it. /ID byte
 * strings are emitted as uppercase hex. Missing /ID emits ``id_present=false``.
 */
public final class FileIdProbe {

    private static void emitId(String prefix, COSArray id) {
        if (id == null || id.size() != 2) {
            System.out.println(prefix + "id_present=false");
            if (id != null) {
                System.out.println(prefix + "id_size=" + id.size());
            }
            return;
        }
        COSBase b0 = id.getObject(0);
        COSBase b1 = id.getObject(1);
        if (!(b0 instanceof COSString) || !(b1 instanceof COSString)) {
            System.out.println(prefix + "id_present=false");
            System.out.println(prefix + "id_nonstring=true");
            return;
        }
        byte[] e0 = ((COSString) b0).getBytes();
        byte[] e1 = ((COSString) b1).getBytes();
        System.out.println(prefix + "id_present=true");
        System.out.println(prefix + "id0_hex=" + hex(e0));
        System.out.println(prefix + "id1_hex=" + hex(e1));
        System.out.println(prefix + "id0_len=" + e0.length);
        System.out.println(prefix + "id1_len=" + e1.length);
        System.out.println(prefix + "id0_eq_id1=" + java.util.Arrays.equals(e0, e1));
    }

    private static String hex(byte[] data) {
        StringBuilder sb = new StringBuilder(data.length * 2);
        for (byte b : data) {
            sb.append(String.format("%02X", b & 0xFF));
        }
        return sb.toString();
    }

    private static COSArray idOf(PDDocument doc) {
        COSBase id = doc.getDocument().getTrailer()
                .getDictionaryObject(COSName.ID);
        return (id instanceof COSArray) ? (COSArray) id : null;
    }

    public static void main(String[] args) throws Exception {
        String mode = args[0];
        if ("read".equals(mode)) {
            try (PDDocument doc = Loader_load(args[1])) {
                emitId("", idOf(doc));
            }
        } else if ("save".equals(mode)) {
            try (PDDocument doc = Loader_load(args[1])) {
                doc.save(new File(args[2]));
            }
            try (PDDocument doc = Loader_load(args[2])) {
                emitId("", idOf(doc));
            }
        } else if ("incremental".equals(mode)) {
            String src0, src1;
            try (PDDocument doc = Loader_load(args[1])) {
                COSArray before = idOf(doc);
                src0 = before == null ? null
                        : hex(((COSString) before.getObject(0)).getBytes());
                src1 = before == null ? null
                        : hex(((COSString) before.getObject(1)).getBytes());
                PDDocumentCatalog catalog = doc.getDocumentCatalog();
                catalog.getCOSObject().setInt(COSName.getPDFName("Version"), 1);
                catalog.getCOSObject().setNeedToBeUpdated(true);
                try (FileOutputStream out = new FileOutputStream(new File(args[2]))) {
                    doc.saveIncremental(out);
                }
            }
            System.out.println("before_id0_hex=" + src0);
            System.out.println("before_id1_hex=" + src1);
            try (PDDocument doc = Loader_load(args[2])) {
                emitId("after_", idOf(doc));
            }
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    // Small shim so the three modes share one loader call site.
    private static PDDocument Loader_load(String path) throws Exception {
        return org.apache.pdfbox.Loader.loadPDF(new File(path));
    }
}
