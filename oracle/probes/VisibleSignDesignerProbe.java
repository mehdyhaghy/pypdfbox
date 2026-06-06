import java.awt.geom.AffineTransform;
import java.lang.reflect.Field;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.visible.PDVisibleSignDesigner;

/**
 * Differential probe for PDVisibleSignDesigner geometry.
 *
 * Mode "rotate" (default, 7 args):
 *   rotate rotation pageWidth pageHeight imageWidth imageHeight xAxis yAxis
 *   (the leading "rotate" token is optional for backward compatibility)
 *   Sets the private rotation/image/page fields via reflection (the public
 *   constructors require a real PDF + image), sets coordinates, runs
 *   adjustForRotation(), and prints the resulting geometry plus the affine
 *   transform and formatter rectangle so pypdfbox can be compared 1:1.
 *
 * Mode "zoom" (4 args):
 *   zoom imageWidth imageHeight percent
 *   Calls width()/height() then zoom(percent) and prints the resulting
 *   single-precision width/height plus the formatter rectangle so the
 *   float32 (int) cast can be pinned exactly.
 */
public class VisibleSignDesignerProbe {
    private static void setFloat(PDVisibleSignDesigner d, String name, float v) throws Exception {
        Field f = PDVisibleSignDesigner.class.getDeclaredField(name);
        f.setAccessible(true);
        f.set(d, v);
    }

    private static void setInt(PDVisibleSignDesigner d, String name, int v) throws Exception {
        Field f = PDVisibleSignDesigner.class.getDeclaredField(name);
        f.setAccessible(true);
        f.set(d, v);
    }

    public static void main(String[] args) throws Exception {
        if (args.length > 0 && args[0].equals("zoom")) {
            zoomMode(args);
            return;
        }
        int base = (args.length > 0 && args[0].equals("rotate")) ? 1 : 0;
        int rotation = Integer.parseInt(args[base]);
        float pageWidth = Float.parseFloat(args[base + 1]);
        float pageHeight = Float.parseFloat(args[base + 2]);
        float imageWidth = Float.parseFloat(args[base + 3]);
        float imageHeight = Float.parseFloat(args[base + 4]);
        float xAxis = Float.parseFloat(args[base + 5]);
        float yAxis = Float.parseFloat(args[base + 6]);

        // The InputStream constructor only reads an image; feed it a 1x1 PNG so
        // setImage succeeds, then override the geometry fields via reflection.
        PDVisibleSignDesigner d =
                new PDVisibleSignDesigner(new java.io.ByteArrayInputStream(onePxPng()));

        setInt(d, "rotation", rotation);
        d.pageWidth(pageWidth);
        setFloat(d, "pageHeight", pageHeight);
        // width()/height() also populate formatterRectangleParameters[2]/[3].
        d.width(imageWidth);
        d.height(imageHeight);
        d.coordinates(xAxis, yAxis);
        d.adjustForRotation();

        AffineTransform t = d.getTransform();
        double[] m = new double[6];
        t.getMatrix(m);
        int[] r = d.getFormatterRectangleParameters();
        System.out.printf(
                "x=%s y=%s w=%s h=%s m00=%s m10=%s m01=%s m11=%s m02=%s m12=%s rect=%d,%d,%d,%d%n",
                fmt(d.getxAxis()), fmt(d.getyAxis()), fmt(d.getWidth()), fmt(d.getHeight()),
                fmt(m[0]), fmt(m[1]), fmt(m[2]), fmt(m[3]), fmt(m[4]), fmt(m[5]),
                r[0], r[1], r[2], r[3]);
    }

    private static void zoomMode(String[] args) throws Exception {
        float imageWidth = Float.parseFloat(args[1]);
        float imageHeight = Float.parseFloat(args[2]);
        float percent = Float.parseFloat(args[3]);

        PDVisibleSignDesigner d =
                new PDVisibleSignDesigner(new java.io.ByteArrayInputStream(onePxPng()));
        d.width(imageWidth);
        d.height(imageHeight);
        d.zoom(percent);

        int[] r = d.getFormatterRectangleParameters();
        System.out.printf(
                "w=%s h=%s rect=%d,%d,%d,%d%n",
                fmt(d.getWidth()), fmt(d.getHeight()), r[0], r[1], r[2], r[3]);
    }

    private static String fmt(double v) {
        return String.valueOf((float) v);
    }

    private static byte[] onePxPng() throws Exception {
        java.awt.image.BufferedImage img =
                new java.awt.image.BufferedImage(1, 1, java.awt.image.BufferedImage.TYPE_INT_RGB);
        java.io.ByteArrayOutputStream bos = new java.io.ByteArrayOutputStream();
        javax.imageio.ImageIO.write(img, "png", bos);
        return bos.toByteArray();
    }
}
