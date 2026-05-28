import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

/**
 * Live oracle probe: emit Apache PDFBox's page /Thumb metadata.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PageThumbProbe input.pdf
 * Output (UTF-8, to stdout): one line per page.
 *   absent /Thumb     -> "page <i> thumb none"
 *   present /Thumb    -> "page <i> thumb present w <w> h <h> bpc <bpc> cs <cs>"
 *
 * /Thumb is read directly off the page's COS dictionary so upstream's
 * "thumbnails are special — any non-null subtype is treated as Image"
 * rule applies (we wrap the stream with PDImageXObject.createThumbnail).
 * w/h/bpc are the public accessors; cs is the resolved getColorSpace().
 * getName() (or "null" when the typed wrapper can't resolve).
 */
public final class PageThumbProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int count = doc.getNumberOfPages();
            for (int i = 0; i < count; i++) {
                PDPage page = doc.getPage(i);
                COSDictionary dict = page.getCOSObject();
                COSBase raw = dict.getDictionaryObject(COSName.THUMB);
                if (!(raw instanceof COSStream)) {
                    out.println("page " + i + " thumb none");
                    continue;
                }
                PDImageXObject thumb = PDImageXObject.createThumbnail((COSStream) raw);
                int w = thumb.getWidth();
                int h = thumb.getHeight();
                int bpc = thumb.getBitsPerComponent();
                String cs;
                try {
                    PDColorSpace colorSpace = thumb.getColorSpace();
                    cs = colorSpace != null ? colorSpace.getName() : "null";
                } catch (Exception ex) {
                    cs = "null";
                }
                out.println("page " + i + " thumb present"
                          + " w " + w
                          + " h " + h
                          + " bpc " + bpc
                          + " cs " + cs);
            }
        }
    }
}
