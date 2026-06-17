import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.util.Base64;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;
import org.apache.pdfbox.pdmodel.graphics.image.LosslessFactory;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for differential FUZZING of the high-level
 * {@code PDPageContentStream} IMAGE + FORM drawing API against PDFBox 3.0.7.
 *
 * Sibling to {@code DrawImageProbe} (which pins three fixed overloads + the
 * resource registration) and {@code ContentStreamGenFuzzProbe} (text / path /
 * colour fuzz). This probe drives a battery of ~30 image/form edge cases and,
 * for each, projects EITHER the exact emitted content-stream bytes (base64)
 * followed by the page's {@code /XObject} resource keys, OR the exception class
 * + message if the call sequence throws. One result per line:
 *
 *     &lt;case-name&gt;\tOK\t&lt;base64-of-stream-bytes&gt;\t&lt;xobject-keys-csv&gt;
 *     &lt;case-name&gt;\tEXC\t&lt;exception-class&gt;\t&lt;message&gt;
 *
 * Edge angles (NOT covered by DrawImageProbe's three fixed overloads):
 *   - drawImage(x, y, w, h) with zero / negative / fractional / huge w/h
 *   - drawImage(Matrix) with singular / extreme / negative matrices
 *   - NaN / +Inf / -Inf coordinates (should raise — pin)
 *   - drawForm of a form XObject (bare /Name Do, no q/cm/Q)
 *   - image resource-name allocation (Im1 reuse drawing the same image twice)
 *   - drawing two distinct images (Im1 + Im2)
 *   - text-block guard (drawImage / drawForm inside BT/ET → raise)
 *
 * The paired pytest reproduces the identical sequences with pypdfbox and
 * asserts the projection matches line-for-line (the auto-allocated XObject key
 * starts at Im1 / Form1 on both sides).
 *
 * Usage: java DrawImageGenFuzzProbe
 */
public final class DrawImageGenFuzzProbe {

    private static final PrintStream OUT;
    static {
        OUT = new PrintStream(System.out, true, java.nio.charset.StandardCharsets.UTF_8);
    }

    /** A drawing script that mutates a PDPageContentStream. */
    private interface Script {
        void run(PDDocument doc, PDPage page, PDPageContentStream cs) throws Exception;
    }

    public static void main(String[] args) throws Exception {
        // --- drawImage(image, x, y, w, h) numeric edge cases ---
        run("xywh_basic", (d, p, cs) -> cs.drawImage(img(d), 10f, 20f, 100f, 50f));
        run("xywh_zero_size", (d, p, cs) -> cs.drawImage(img(d), 5f, 5f, 0f, 0f));
        run("xywh_negative_size", (d, p, cs) -> cs.drawImage(img(d), 5f, 5f, -100f, -50f));
        run("xywh_fractional", (d, p, cs) -> cs.drawImage(img(d), 1.5f, 2.5f, 12.345f, 6.789f));
        run("xywh_huge", (d, p, cs) -> cs.drawImage(img(d), 0f, 0f, 1.0e9f, 1.0e9f));
        run("xywh_tiny", (d, p, cs) -> cs.drawImage(img(d), 0.000005f, 0f, 0.000004f, 0.123455f));
        run("xywh_negative_origin", (d, p, cs) -> cs.drawImage(img(d), -50f, -60f, 100f, 50f));

        // --- drawImage(image, x, y) native-size overload ---
        run("xy_basic", (d, p, cs) -> cs.drawImage(img(d), 10f, 20f));
        run("xy_origin", (d, p, cs) -> cs.drawImage(img(d), 0f, 0f));
        run("xy_fractional", (d, p, cs) -> cs.drawImage(img(d), 7.25f, 11.75f));

        // --- drawImage(image, Matrix) overload ---
        run("matrix_basic", (d, p, cs) ->
                cs.drawImage(img(d), new Matrix(2f, 0.5f, 0.25f, 3f, 7f, 11f)));
        run("matrix_identity", (d, p, cs) ->
                cs.drawImage(img(d), new Matrix(1f, 0f, 0f, 1f, 0f, 0f)));
        run("matrix_singular", (d, p, cs) ->
                cs.drawImage(img(d), new Matrix(0f, 0f, 0f, 0f, 0f, 0f)));
        run("matrix_negative_scale", (d, p, cs) ->
                cs.drawImage(img(d), new Matrix(-100f, 0f, 0f, -50f, 50f, 60f)));
        run("matrix_rotate", (d, p, cs) ->
                cs.drawImage(img(d), new Matrix(0f, 100f, -100f, 0f, 50f, 60f)));
        run("matrix_extreme", (d, p, cs) ->
                cs.drawImage(img(d), new Matrix(1.0e6f, 0f, 0f, 1.0e6f, -50000.25f, 0.000001f)));
        run("matrix_shear", (d, p, cs) ->
                cs.drawImage(img(d), new Matrix(1f, 0.5f, 0.5f, 1f, 0f, 0f)));

        // --- NaN / Infinity coordinates (should raise) ---
        run("xy_nan_x", (d, p, cs) -> cs.drawImage(img(d), Float.NaN, 20f));
        run("xy_pos_inf_y", (d, p, cs) -> cs.drawImage(img(d), 10f, Float.POSITIVE_INFINITY));
        run("xywh_neg_inf_w", (d, p, cs) ->
                cs.drawImage(img(d), 0f, 0f, Float.NEGATIVE_INFINITY, 50f));
        run("matrix_nan_e", (d, p, cs) ->
                cs.drawImage(img(d), new Matrix(1f, 0f, 0f, 1f, Float.NaN, 0f)));

        // --- drawForm ---
        run("draw_form_basic", (d, p, cs) -> cs.drawForm(form(d)));

        // --- resource-name allocation ---
        run("same_image_twice", (d, p, cs) -> {
            PDImageXObject im = img(d);
            cs.drawImage(im, 0f, 0f, 10f, 10f);
            cs.drawImage(im, 20f, 20f, 10f, 10f);
        });
        run("two_distinct_images", (d, p, cs) -> {
            cs.drawImage(img(d), 0f, 0f, 10f, 10f);
            cs.drawImage(img(d), 20f, 20f, 10f, 10f);
        });
        run("image_then_form", (d, p, cs) -> {
            cs.drawImage(img(d), 0f, 0f, 10f, 10f);
            cs.drawForm(form(d));
        });
        run("form_twice_same", (d, p, cs) -> {
            PDFormXObject f = form(d);
            cs.drawForm(f);
            cs.drawForm(f);
        });

        // --- text-block guards ---
        run("draw_image_in_text_block", (d, p, cs) -> {
            cs.beginText();
            cs.drawImage(img(d), 0f, 0f);
        });
        run("draw_form_in_text_block", (d, p, cs) -> {
            cs.beginText();
            cs.drawForm(form(d));
        });

        // --- q/Q surrounding then drawImage (state stack) ---
        run("save_then_draw_image", (d, p, cs) -> {
            cs.saveGraphicsState();
            cs.drawImage(img(d), 1f, 2f, 3f, 4f);
            cs.restoreGraphicsState();
        });

        OUT.flush();
    }

    /** A deterministic 4x3 ARGB image with a fixed pixel pattern. */
    private static PDImageXObject img(PDDocument doc) throws Exception {
        BufferedImage bi = new BufferedImage(4, 3, BufferedImage.TYPE_INT_ARGB);
        for (int y = 0; y < 3; y++) {
            for (int x = 0; x < 4; x++) {
                bi.setRGB(x, y, 0xFF000000 | (x * 40) << 16 | (y * 60) << 8 | 0x33);
            }
        }
        return LosslessFactory.createFromImage(doc, bi);
    }

    /** A minimal empty form XObject with a 0 0 8 8 bbox. */
    private static PDFormXObject form(PDDocument doc) {
        PDFormXObject f = new PDFormXObject(doc);
        f.setBBox(new org.apache.pdfbox.pdmodel.common.PDRectangle(0, 0, 8, 8));
        return f;
    }

    /** Run one script; project bytes + xobject keys, or exception. */
    private static void run(String name, Script script) {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                script.run(doc, page, cs);
            }
            PDStream contents = page.getContentStreams().next();
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            try (var in = contents.createInputStream()) {
                in.transferTo(baos);
            }
            byte[] bytes = baos.toByteArray();
            StringBuilder keys = new StringBuilder();
            PDResources res = page.getResources();
            boolean first = true;
            for (org.apache.pdfbox.cos.COSName n : res.getXObjectNames()) {
                if (!first) {
                    keys.append(',');
                }
                keys.append(n.getName());
                first = false;
            }
            OUT.println(name + "\tOK\t" + Base64.getEncoder().encodeToString(bytes)
                    + "\t" + keys);
        } catch (Throwable t) {
            String msg = t.getMessage();
            OUT.println(name + "\tEXC\t" + t.getClass().getSimpleName()
                    + "\t" + (msg == null ? "" : msg.replace('\n', ' ').replace('\t', ' ')));
        }
    }
}
