import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.multipdf.Splitter;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe pinning PDFBox's {@link Splitter} *inherited page-geometry
 * materialisation*. Upstream's {@code PDDocument.importPage} (which Splitter
 * drives per page) re-applies {@code setCropBox} / {@code setMediaBox} /
 * {@code setRotation} from the resolved source values right after detaching the
 * page from its parent tree, so a page that inherited its /MediaBox, /CropBox or
 * /Rotate from a page-tree node still carries concrete values on its own dict in
 * the split output.
 *
 * For each split part this probe emits, per page: the resolved MediaBox + CropBox
 * rectangles (rounded to keep the comparison stable), the resolved /Rotate, and
 * whether the /MediaBox + /CropBox keys are materialised directly on the page
 * dictionary (not inherited). pypdfbox must match every field.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> SplitterInheritProbe in.pdf <splitAtPage>
 *
 * Output (UTF-8): a JSON object
 *   {"parts":[{"pages":[{"mb":[x,y,w,h],"cb":[x,y,w,h],"rot":R,
 *                        "mbKey":true,"cbKey":true}, ...]}, ...]}
 */
public final class SplitterInheritProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int splitAt = Integer.parseInt(args[1]);

        try (PDDocument source = Loader.loadPDF(new File(args[0]))) {
            Splitter splitter = new Splitter();
            splitter.setSplitAtPage(splitAt);
            List<PDDocument> parts = splitter.split(source);

            StringBuilder sb = new StringBuilder();
            sb.append("{\"parts\":[");
            try {
                for (int i = 0; i < parts.size(); i++) {
                    PDDocument part = parts.get(i);
                    if (i > 0) {
                        sb.append(',');
                    }
                    sb.append("{\"pages\":[");
                    int p = 0;
                    for (PDPage page : part.getPages()) {
                        if (p++ > 0) {
                            sb.append(',');
                        }
                        emitPage(sb, page);
                    }
                    sb.append("]}");
                }
            } finally {
                for (PDDocument part : parts) {
                    part.close();
                }
            }
            sb.append("]}");
            out.print(sb);
        }
    }

    private static void emitPage(StringBuilder sb, PDPage page) {
        PDRectangle mb = page.getMediaBox();
        PDRectangle cb = page.getCropBox();
        sb.append("{\"mb\":");
        emitRect(sb, mb);
        sb.append(",\"cb\":");
        emitRect(sb, cb);
        sb.append(",\"rot\":").append(page.getRotation());
        sb.append(",\"mbKey\":")
          .append(page.getCOSObject().containsKey(COSName.MEDIA_BOX));
        sb.append(",\"cbKey\":")
          .append(page.getCOSObject().containsKey(COSName.CROP_BOX));
        sb.append('}');
    }

    private static void emitRect(StringBuilder sb, PDRectangle r) {
        sb.append('[')
          .append(round(r.getLowerLeftX())).append(',')
          .append(round(r.getLowerLeftY())).append(',')
          .append(round(r.getWidth())).append(',')
          .append(round(r.getHeight()))
          .append(']');
    }

    private static long round(float v) {
        return Math.round(v);
    }
}
