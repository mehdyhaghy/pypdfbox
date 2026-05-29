import java.io.File;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;

/**
 * Live oracle probe for the trailer /ID *synthesis* path and cross-readability,
 * complementing FileIdProbe (which exercises read / preserve / incremental on
 * fixtures that already carry an /ID).
 *
 * This probe targets the branch FileIdProbe never hits: a document that lacks
 * an /ID. ISO 32000-1 §14.4 / PDF §7.5.5 — when a producer writes a file with
 * no existing identifier it synthesises a 2-element array whose two halves are
 * *identical* (the permanent and changing identifiers start equal). PDFBox
 * builds this in COSWriter via an MD5 over (current time + file size + Info
 * dict). The value is time-based so a parity test asserts STRUCTURE, not bytes.
 *
 * Modes (args[0]):
 *
 *   freshsave  out.pdf
 *       Create a brand-new PDDocument (one blank page, no /ID), save it to
 *       out.pdf, reload, and emit the synthesised /ID facts. Used to confirm
 *       PDFBox synthesises [id id] with both halves identical and 16 bytes.
 *
 *   read  in.pdf
 *       Load in.pdf and emit its trailer /ID facts. Used for cross-readability:
 *       feed a pypdfbox-saved file here and confirm PDFBox parses the same /ID.
 *
 * Output is line-oriented ``key=value``. /ID byte strings are emitted as
 * uppercase hex. Missing /ID emits ``id_present=false``.
 */
public final class FileIdSynthProbe {

    private static void emitId(COSArray id) {
        if (id == null || id.size() != 2) {
            System.out.println("id_present=false");
            if (id != null) {
                System.out.println("id_size=" + id.size());
            }
            return;
        }
        COSBase b0 = id.getObject(0);
        COSBase b1 = id.getObject(1);
        if (!(b0 instanceof COSString) || !(b1 instanceof COSString)) {
            System.out.println("id_present=false");
            System.out.println("id_nonstring=true");
            return;
        }
        byte[] e0 = ((COSString) b0).getBytes();
        byte[] e1 = ((COSString) b1).getBytes();
        System.out.println("id_present=true");
        System.out.println("id0_hex=" + hex(e0));
        System.out.println("id1_hex=" + hex(e1));
        System.out.println("id0_len=" + e0.length);
        System.out.println("id1_len=" + e1.length);
        System.out.println("id0_eq_id1=" + java.util.Arrays.equals(e0, e1));
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
        if ("freshsave".equals(mode)) {
            try (PDDocument doc = new PDDocument()) {
                doc.addPage(new PDPage());
                // Confirm the in-memory doc carries no /ID before save.
                System.out.println("pre_id_present="
                        + (idOf(doc) != null));
                doc.save(new File(args[1]));
            }
            try (PDDocument doc = org.apache.pdfbox.Loader.loadPDF(new File(args[1]))) {
                emitId(idOf(doc));
            }
        } else if ("read".equals(mode)) {
            try (PDDocument doc = org.apache.pdfbox.Loader.loadPDF(new File(args[1]))) {
                emitId(idOf(doc));
            }
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }
}
