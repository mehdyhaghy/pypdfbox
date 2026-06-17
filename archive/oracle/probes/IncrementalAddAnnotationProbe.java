import java.io.File;
import java.io.FileOutputStream;
import java.nio.file.Files;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationText;

/**
 * Live oracle probe for an <b>incremental save that ADDS a brand-new object</b>
 * (a text annotation) to an existing page — as opposed to merely mutating an
 * already-present object (an /Info field, the catalog /Version). The new
 * annotation object must be minted with an object number above the source's
 * highest, the page's /Annots must be appended (it gains the new ref), and the
 * whole thing must round-trip through a reload with the original bytes intact
 * as a prefix.
 *
 * Modes (args[0]):
 *
 *   addincr  in.pdf out.pdf
 *       Load in.pdf, add a PDAnnotationText to page 0 (rect 50 50 100 100,
 *       Contents "IncAnnot"), flag the page + annotation dirty, incremental-
 *       save to out.pdf. Then reload out.pdf and emit the facts a parity test
 *       checks: prefix preservation, page count, the annotation's recovered
 *       subtype/contents/rect, the trailer /ID contract, and /Prev presence.
 *
 * Output is line-oriented UTF-8 ``key=value``. /ID byte strings are uppercase
 * hex; a missing /ID emits ``id_present=false``.
 */
public final class IncrementalAddAnnotationProbe {

    private static String hex(byte[] data) {
        StringBuilder sb = new StringBuilder(data.length * 2);
        for (byte b : data) {
            sb.append(String.format("%02X", b & 0xFF));
        }
        return sb.toString();
    }

    private static COSArray idOf(PDDocument doc) {
        COSBase id = doc.getDocument().getTrailer().getDictionaryObject(COSName.ID);
        return (id instanceof COSArray) ? (COSArray) id : null;
    }

    public static void main(String[] args) throws Exception {
        String mode = args[0];
        if (!"addincr".equals(mode)) {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
        File src = new File(args[1]);
        File out = new File(args[2]);
        byte[] srcBytes = Files.readAllBytes(src.toPath());

        // --- capture source /ID ---
        String beforeId0;
        String beforeId1;
        try (PDDocument doc = Loader.loadPDF(src)) {
            COSArray before = idOf(doc);
            beforeId0 = before == null ? "NULL"
                    : hex(((COSString) before.getObject(0)).getBytes());
            beforeId1 = before == null ? "NULL"
                    : hex(((COSString) before.getObject(1)).getBytes());

            // --- add a brand-new annotation object to page 0 ---
            PDPage page = doc.getPage(0);
            PDAnnotationText annot = new PDAnnotationText();
            annot.setContents("IncAnnot");
            annot.setRectangle(new PDRectangle(50, 50, 50, 50));
            page.getAnnotations().add(annot);
            // Flag the page dirty so the appended /Annots ref is written, and
            // flag the annotation dirty so the new object body is emitted.
            page.getCOSObject().setNeedToBeUpdated(true);
            annot.getCOSObject().setNeedToBeUpdated(true);

            try (FileOutputStream os = new FileOutputStream(out)) {
                doc.saveIncremental(os);
            }
        }

        byte[] outBytes = Files.readAllBytes(out.toPath());
        boolean prefixOk = outBytes.length >= srcBytes.length;
        if (prefixOk) {
            for (int i = 0; i < srcBytes.length; i++) {
                if (outBytes[i] != srcBytes[i]) {
                    prefixOk = false;
                    break;
                }
            }
        }
        // /Prev must appear in the appended tail (the new revision's trailer).
        byte[] tail = new byte[outBytes.length - srcBytes.length];
        System.arraycopy(outBytes, srcBytes.length, tail, 0, tail.length);
        boolean prevInTail = new String(tail, "ISO-8859-1").contains("/Prev");

        StringBuilder sb = new StringBuilder();
        sb.append("prefix_preserved=").append(prefixOk).append("\n");
        sb.append("grew=").append(outBytes.length > srcBytes.length).append("\n");
        sb.append("prev_in_tail=").append(prevInTail).append("\n");
        sb.append("before_id0_hex=").append(beforeId0).append("\n");
        sb.append("before_id1_hex=").append(beforeId1).append("\n");

        // --- reload the incremental output and read the new annotation back ---
        try (PDDocument doc = Loader.loadPDF(out)) {
            sb.append("pages=").append(doc.getNumberOfPages()).append("\n");
            PDPage page = doc.getPage(0);
            int count = page.getAnnotations().size();
            sb.append("annot_count=").append(count).append("\n");
            String subtype = "NULL";
            String contents = "NULL";
            String rect = "NULL";
            for (PDAnnotation a : page.getAnnotations()) {
                if ("IncAnnot".equals(a.getContents())) {
                    subtype = a.getSubtype();
                    contents = a.getContents();
                    PDRectangle r = a.getRectangle();
                    if (r != null) {
                        rect = ((int) r.getLowerLeftX()) + ","
                                + ((int) r.getLowerLeftY()) + ","
                                + ((int) r.getUpperRightX()) + ","
                                + ((int) r.getUpperRightY());
                    }
                }
            }
            sb.append("annot_subtype=").append(subtype).append("\n");
            sb.append("annot_contents=").append(contents).append("\n");
            sb.append("annot_rect=").append(rect).append("\n");

            COSArray after = idOf(doc);
            if (after == null || after.size() != 2) {
                sb.append("after_id_present=false\n");
            } else {
                sb.append("after_id_present=true\n");
                sb.append("after_id0_hex=")
                        .append(hex(((COSString) after.getObject(0)).getBytes()))
                        .append("\n");
                sb.append("after_id1_hex=")
                        .append(hex(((COSString) after.getObject(1)).getBytes()))
                        .append("\n");
            }
        }
        System.out.print(sb);
    }
}
