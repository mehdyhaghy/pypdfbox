import java.awt.geom.AffineTransform;
import java.lang.reflect.Field;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.visible.PDVisibleSignDesigner;

/**
 * Differential probe for PDVisibleSignDesigner geometry.
 *
 * args: rotation pageWidth pageHeight imageWidth imageHeight xAxis yAxis
 *
 * Sets the private rotation/image/page fields via reflection (the public
 * constructors require a real PDF + image), sets coordinates, runs
 * adjustForRotation(), and prints the resulting geometry plus the affine
 * transform and formatter rectangle so pypdfbox can be compared 1:1.
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
        int rotation = Integer.parseInt(args[0]);
        float pageWidth = Float.parseFloat(args[1]);
        float pageHeight = Float.parseFloat(args[2]);
        float imageWidth = Float.parseFloat(args[3]);
        float imageHeight = Float.parseFloat(args[4]);
        float xAxis = Float.parseFloat(args[5]);
        float yAxis = Float.parseFloat(args[6]);

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
