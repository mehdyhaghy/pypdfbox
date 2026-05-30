import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

/**
 * Live oracle probe: decode a 1-component Separation Image XObject through
 * Apache PDFBox and emit sampled RGB pixels from its decoded raster so a test
 * can verify pypdfbox applies the image's {@code /Decode} array (including an
 * inverted {@code [1 0]}) BEFORE the Separation tint transform runs.
 *
 * PDFBox's SampledImageReader maps every raw sample through
 * {@code decode[0] + sample/maxVal * (decode[1] - decode[0])} into the colour
 * space's component range before PDSeparation.toRGBImage evaluates the tint
 * transform; a {@code /Decode [1 0]} therefore reverses the tint ramp.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SeparationDecodeImageProbe in.pdf
 * Output (UTF-8, to stdout), one line per Image XObject found by walking every
 * page's PDResources.getXObjectNames():
 *   "image page <p> name <n> w <w> h <h> cs <cs> row <r,g,b r,g,b ...>"
 * where the row is every pixel of the image's middle scanline, sampled as
 * comma-joined R,G,B triples (space-separated between pixels).
 */
public final class SeparationDecodeImageProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int count = doc.getNumberOfPages();
            for (int p = 0; p < count; p++) {
                PDPage page = doc.getPage(p);
                PDResources res = page.getResources();
                if (res == null) {
                    continue;
                }
                for (COSName name : res.getXObjectNames()) {
                    PDXObject xobject = res.getXObject(name);
                    if (!(xobject instanceof PDImageXObject)) {
                        continue;
                    }
                    emit(out, p, name.getName(), (PDImageXObject) xobject);
                }
            }
        }
    }

    private static void emit(PrintStream out, int page, String name,
                             PDImageXObject image) throws Exception {
        int w = image.getWidth();
        int h = image.getHeight();
        String cs = image.getColorSpace() != null
                ? image.getColorSpace().getName() : "null";
        BufferedImage img = image.getImage();
        int iw = img.getWidth();
        int ih = img.getHeight();
        int midY = ih / 2;
        StringBuilder sb = new StringBuilder();
        sb.append("image page ").append(page)
          .append(" name ").append(name)
          .append(" w ").append(w)
          .append(" h ").append(h)
          .append(" cs ").append(cs)
          .append(" row ");
        for (int x = 0; x < iw; x++) {
            if (x > 0) {
                sb.append(' ');
            }
            int rgb = img.getRGB(x, midY);
            int r = (rgb >> 16) & 0xFF;
            int g = (rgb >> 8) & 0xFF;
            int b = rgb & 0xFF;
            sb.append(r).append(',').append(g).append(',').append(b);
        }
        out.println(sb.toString());
    }
}
