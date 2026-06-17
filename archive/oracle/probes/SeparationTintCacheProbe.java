import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.graphics.color.PDSeparation;

/**
 * Live oracle probe for two under-pinned aspects of {@link PDSeparation#toRGB}:
 *
 * <ol>
 *   <li><b>Out-of-[0,1] tint clamping.</b> {@code toRGB} forwards the tint to
 *       {@code tintTransform.eval(value)}. {@code PDFunction.eval} clips each
 *       input to the function {@code /Domain} (here {@code [0 1]}) BEFORE
 *       evaluating (PDFunction.java {@code clipToRange}). So a tint of
 *       {@code 1.5} behaves exactly like {@code 1.0}, and {@code -0.5} like
 *       {@code 0.0}. We assert that empirically.</li>
 *   <li><b>Quantised cache key collision.</b> {@code toRGB} caches results in a
 *       {@code Map<Integer,float[]>} keyed on {@code (int)(value[0] * 255)}
 *       (PDSeparation.java line 143). Two distinct tints that land on the SAME
 *       truncated key return the value computed for whichever tint was seen
 *       FIRST — even when the underlying (non-linear) tint transform would
 *       otherwise give a different RGB. With a non-linear Type-2 transform
 *       (N != 1) two close tints (0.500 and 0.5039) share key 127, so the
 *       second call returns the first's RGB. We emit calls in a fixed order so
 *       the Python side can reproduce the exact same cache-population sequence
 *       on its own {@code to_rgb} and compare byte-for-byte.</li>
 * </ol>
 *
 * <p>The alternate colour space is DeviceRGB so the tint-transform output flows
 * straight through {@code DeviceRGB.toRGB} (identity, no CMM) — every emitted
 * RGB is therefore deterministic float arithmetic identical on both sides, so
 * this is an EXACT-match probe (no documented CMM divergence tier needed).
 *
 * <p>The tint transform is a Type-2 exponential function:
 * {@code C0=[0 0 0], C1=[1 0.5 0.25], N=2} on {@code /Domain [0 1]}, giving
 * {@code rgb = [t^2, 0.5*t^2, 0.25*t^2]} for a clipped tint {@code t}.
 *
 * <p>Each line is {@code "tag tint -> r g b"} (RGB 0-255 ints,
 * {@code round(component*255)} clamped to {@code [0,255]}); the tint token is
 * the exact float literal so Python can rebuild it.
 */
public final class SeparationTintCacheProbe {

    static PrintStream out;

    static PDSeparation make() throws Exception {
        COSArray arr = new COSArray();
        arr.add(COSName.SEPARATION);
        arr.add(COSName.getPDFName("Spot"));
        arr.add(COSName.DEVICERGB);

        COSDictionary fn = new COSDictionary();
        fn.setItem(COSName.FUNCTION_TYPE, COSInteger.get(2));
        COSArray domain = new COSArray();
        domain.add(new COSFloat(0f));
        domain.add(new COSFloat(1f));
        fn.setItem(COSName.DOMAIN, domain);
        COSArray c0 = new COSArray();
        c0.add(new COSFloat(0f));
        c0.add(new COSFloat(0f));
        c0.add(new COSFloat(0f));
        fn.setItem(COSName.C0, c0);
        COSArray c1 = new COSArray();
        c1.add(new COSFloat(1f));
        c1.add(new COSFloat(0.5f));
        c1.add(new COSFloat(0.25f));
        fn.setItem(COSName.C1, c1);
        fn.setItem(COSName.N, new COSFloat(2f));
        arr.add(fn);

        return new PDSeparation(arr, null);
    }

    static int clamp255(float v) {
        int r = Math.round(v * 255f);
        if (r < 0) return 0;
        if (r > 255) return 255;
        return r;
    }

    static void emit(PDSeparation cs, String tag, float tint) throws Exception {
        float[] rgb = cs.toRGB(new float[] { tint });
        out.println(tag + " " + tint + " -> "
                + clamp255(rgb[0]) + " " + clamp255(rgb[1]) + " " + clamp255(rgb[2]));
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---- (1) out-of-range clamping: a FRESH space each time so the cache
        // never masks the clamp behaviour. tint 1.5 == 1.0, -0.5 == 0.0.
        emit(make(), "OOR", -0.5f);
        emit(make(), "OOR", 0.0f);
        emit(make(), "OOR", 1.0f);
        emit(make(), "OOR", 1.5f);
        emit(make(), "OOR", 2.0f);
        emit(make(), "OOR", -10.0f);

        // ---- (2) cache-collision sequence on ONE shared space. The order is
        // load-bearing: 0.5f populates key 127; 0.5039f (also key 127) then
        // returns the CACHED 0.5f result, not its own t^2. A later in-range
        // 0.75f is a distinct key (191) so it computes fresh.
        PDSeparation shared = make();
        emit(shared, "CACHE", 0.5f);     // key 127 -> computed fresh
        emit(shared, "CACHE", 0.5039f);  // key 127 -> CACHE HIT (returns 0.5f rgb)
        emit(shared, "CACHE", 0.75f);    // key 191 -> computed fresh
        emit(shared, "CACHE", 0.7505f);  // key 191 -> CACHE HIT (returns 0.75f rgb)
        // out-of-range on the shared space: 1.5f -> key 382, distinct, fresh,
        // but eval clips to 1.0 so rgb == the 1.0 result.
        emit(shared, "CACHE", 1.5f);
    }
}
