import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;
import org.apache.pdfbox.tools.ImageToPDF;
import picocli.CommandLine;

/**
 * Live oracle probe: Apache PDFBox's {@code org.apache.pdfbox.tools.ImageToPDF}
 * — build a single-page PDF from one image file with default settings (Letter
 * media box, no resize, no orientation change). The image is drawn at the
 * lower-left at its intrinsic pixel size via a {@code /Do} on an image XObject.
 *
 * Driven through picocli's {@code CommandLine.execute} (rather than
 * {@code ImageToPDF.main}, which calls {@code System.exit}) so the genuine
 * upstream {@code call()} runs in-process; the result PDF is then reloaded and
 * a canonical structural summary is emitted:
 *
 * <pre>
 *   pages=&lt;n&gt;
 *   mediabox=&lt;llx&gt;,&lt;lly&gt;,&lt;urx&gt;,&lt;ury&gt;     (rounded to 2 decimals)
 *   xobject=&lt;true|false&gt;                     (an image XObject present on page 1)
 *   imgsize=&lt;width&gt;x&lt;height&gt;                  (image XObject pixel dimensions)
 * </pre>
 *
 * Usage: java -cp ... ImageToPdfProbe input.jpg output.pdf
 */
public final class ImageToPdfProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File inFile = new File(args[0]);
        File outFile = new File(args[1]);

        int rc = new CommandLine(new ImageToPDF()).execute(
                "-i", inFile.getAbsolutePath(),
                "-o", outFile.getAbsolutePath());
        if (rc != 0) {
            out.print("exit=" + rc + "\n");
            return;
        }

        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(outFile)) {
            sb.append("pages=").append(doc.getNumberOfPages()).append('\n');

            PDPage page = doc.getPage(0);
            PDRectangle box = page.getMediaBox();
            sb.append("mediabox=")
              .append(fmt(box.getLowerLeftX())).append(',')
              .append(fmt(box.getLowerLeftY())).append(',')
              .append(fmt(box.getUpperRightX())).append(',')
              .append(fmt(box.getUpperRightY())).append('\n');

            boolean hasImage = false;
            String imgSize = "none";
            PDResources res = page.getResources();
            if (res != null) {
                for (COSName name : res.getXObjectNames()) {
                    PDXObject xobj = res.getXObject(name);
                    if (xobj instanceof PDImageXObject) {
                        PDImageXObject img = (PDImageXObject) xobj;
                        hasImage = true;
                        imgSize = img.getWidth() + "x" + img.getHeight();
                        // sanity touch of the underlying COS so a stub would fail
                        COSBase ignored = img.getCOSObject();
                        if (ignored == null) {
                            imgSize = "missing";
                        }
                        break;
                    }
                }
            }
            sb.append("xobject=").append(hasImage).append('\n');
            sb.append("imgsize=").append(imgSize).append('\n');
        }
        out.print(sb);
    }

    private static String fmt(float v) {
        return String.format(java.util.Locale.ROOT, "%.2f", v);
    }
}
