import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.ImageType;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe for Apache PDFBox's {@code org.apache.pdfbox.tools.PDFToImage}
 * render-to-image surface.
 *
 * <p>The tool's {@code call()} renders each page in the {@code [startPage, endPage]}
 * window with {@code PDFRenderer.renderImageWithDPI(i, dpi, imageType)} and writes
 * one output image per page. This probe runs that exact per-page loop (rather than
 * writing image files, which would pull in AWT image codecs / headless concerns)
 * and emits the canonical summary the test compares against:
 *
 * <pre>
 *   count=&lt;number of images produced&gt;
 *   page=&lt;1-based index&gt; &lt;width&gt;x&lt;height&gt;     (one line per rendered page)
 *   ...
 * </pre>
 *
 * Usage: java -cp ... PdfToImageProbe input.pdf dpi startPage endPage
 *   (startPage/endPage 1-based, inclusive; endPage clamped to page count)
 */
public final class PdfToImageProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File inFile = new File(args[0]);
        int dpi = Integer.parseInt(args[1]);
        int startPage = Integer.parseInt(args[2]);
        int endPage = Integer.parseInt(args[3]);

        StringBuilder sb = new StringBuilder();
        try (PDDocument document = Loader.loadPDF(inFile)) {
            int realEnd = Math.min(endPage, document.getNumberOfPages());
            PDFRenderer renderer = new PDFRenderer(document);
            int count = 0;
            StringBuilder pages = new StringBuilder();
            for (int i = startPage - 1; i < realEnd; i++) {
                BufferedImage image = renderer.renderImageWithDPI(i, dpi, ImageType.RGB);
                pages.append("page=").append(i + 1).append(' ')
                     .append(image.getWidth()).append('x').append(image.getHeight())
                     .append('\n');
                count++;
            }
            sb.append("count=").append(count).append('\n');
            sb.append(pages);
        }
        out.print(sb);
    }
}
