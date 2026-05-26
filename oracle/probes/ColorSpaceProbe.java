import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.graphics.color.PDCalGray;
import org.apache.pdfbox.pdmodel.graphics.color.PDCalRGB;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceCMYK;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceGray;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceN;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.graphics.color.PDIndexed;
import org.apache.pdfbox.pdmodel.graphics.color.PDLab;
import org.apache.pdfbox.pdmodel.graphics.color.PDSeparation;

/**
 * Live oracle probe: emit Apache PDFBox's PDColorSpace.toRGB() output as
 * canonical "csname comp... -> r g b" lines (RGB are 0-255 ints).
 *
 * A fixed battery of color spaces and input component tuples is hard-coded so
 * the Python differential test only has to reproduce the matching pypdfbox
 * color spaces and the same inputs. No argv needed.
 *
 * RGB ints are computed exactly as pypdfbox does: round(component * 255),
 * clamped to [0, 255]. PDFBox's own toRGB returns float[] in [0,1].
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ColorSpaceProbe
 */
public final class ColorSpaceProbe {

    static PrintStream out;

    static int clamp255(float v) {
        long r = Math.round((double) v * 255.0);
        if (r < 0) {
            return 0;
        }
        if (r > 255) {
            return 255;
        }
        return (int) r;
    }

    static void emit(String name, float[] comps, PDColorSpace cs) throws Exception {
        float[] rgb = cs.toRGB(comps);
        StringBuilder sb = new StringBuilder();
        sb.append(name);
        for (float c : comps) {
            sb.append(' ').append(fmt(c));
        }
        sb.append(" -> ");
        sb.append(clamp255(rgb[0])).append(' ');
        sb.append(clamp255(rgb[1])).append(' ');
        sb.append(clamp255(rgb[2]));
        out.println(sb.toString());
    }

    static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Integer.toString((int) v);
        }
        return Float.toString(v);
    }

    static COSDictionary type2(float[] c0, float[] c1, float n) {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        COSArray domain = new COSArray();
        domain.add(new COSFloat(0));
        domain.add(new COSFloat(1));
        d.setItem(COSName.DOMAIN, domain);
        COSArray a0 = new COSArray();
        for (float v : c0) {
            a0.add(new COSFloat(v));
        }
        d.setItem(COSName.C0, a0);
        COSArray a1 = new COSArray();
        for (float v : c1) {
            a1.add(new COSFloat(v));
        }
        d.setItem(COSName.C1, a1);
        d.setItem(COSName.N, new COSFloat(n));
        return d;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---------- DeviceGray ----------
        PDDeviceGray gray = PDDeviceGray.INSTANCE;
        emit("DeviceGray", new float[] {0.0f}, gray);
        emit("DeviceGray", new float[] {0.5f}, gray);
        emit("DeviceGray", new float[] {1.0f}, gray);

        // ---------- DeviceRGB ----------
        PDDeviceRGB rgb = PDDeviceRGB.INSTANCE;
        emit("DeviceRGB", new float[] {0.0f, 0.0f, 0.0f}, rgb);
        emit("DeviceRGB", new float[] {1.0f, 0.0f, 0.0f}, rgb);
        emit("DeviceRGB", new float[] {0.25f, 0.5f, 0.75f}, rgb);
        emit("DeviceRGB", new float[] {1.0f, 1.0f, 1.0f}, rgb);

        // ---------- DeviceCMYK ----------
        PDDeviceCMYK cmyk = PDDeviceCMYK.INSTANCE;
        emit("DeviceCMYK", new float[] {0.0f, 0.0f, 0.0f, 0.0f}, cmyk);
        emit("DeviceCMYK", new float[] {0.0f, 0.0f, 0.0f, 1.0f}, cmyk);
        emit("DeviceCMYK", new float[] {1.0f, 1.0f, 1.0f, 1.0f}, cmyk); // registration black
        emit("DeviceCMYK", new float[] {1.0f, 0.0f, 0.0f, 0.0f}, cmyk);
        emit("DeviceCMYK", new float[] {0.0f, 1.0f, 1.0f, 0.0f}, cmyk);
        emit("DeviceCMYK", new float[] {0.2f, 0.4f, 0.6f, 0.1f}, cmyk);

        // ---------- CalGray (with gamma) ----------
        COSArray calGrayArr = new COSArray();
        calGrayArr.add(COSName.CALGRAY);
        COSDictionary calGrayDict = new COSDictionary();
        COSArray wpD65 = new COSArray();
        wpD65.add(new COSFloat(0.9505f));
        wpD65.add(new COSFloat(1.0f));
        wpD65.add(new COSFloat(1.089f));
        calGrayDict.setItem(COSName.WHITE_POINT, wpD65);
        calGrayDict.setItem(COSName.GAMMA, new COSFloat(2.2f));
        calGrayArr.add(calGrayDict);
        PDCalGray calGray = new PDCalGray(calGrayArr);
        emit("CalGray", new float[] {0.0f}, calGray);
        emit("CalGray", new float[] {0.5f}, calGray);
        emit("CalGray", new float[] {1.0f}, calGray);

        // ---------- CalRGB (D65 whitepoint, gamma + identity matrix) ----------
        COSArray calRgbArr = new COSArray();
        calRgbArr.add(COSName.CALRGB);
        COSDictionary calRgbDict = new COSDictionary();
        COSArray wpUnit = new COSArray();
        wpUnit.add(new COSFloat(1.0f));
        wpUnit.add(new COSFloat(1.0f));
        wpUnit.add(new COSFloat(1.0f));
        calRgbDict.setItem(COSName.WHITE_POINT, wpUnit);
        COSArray gammas = new COSArray();
        gammas.add(new COSFloat(1.8f));
        gammas.add(new COSFloat(1.8f));
        gammas.add(new COSFloat(1.8f));
        calRgbDict.setItem(COSName.GAMMA, gammas);
        calRgbArr.add(calRgbDict);
        PDCalRGB calRgb = new PDCalRGB(calRgbArr);
        emit("CalRGB", new float[] {0.0f, 0.0f, 0.0f}, calRgb);
        emit("CalRGB", new float[] {1.0f, 0.0f, 0.0f}, calRgb);
        emit("CalRGB", new float[] {0.5f, 0.5f, 0.5f}, calRgb);
        emit("CalRGB", new float[] {1.0f, 1.0f, 1.0f}, calRgb);

        // ---------- Lab (D50 whitepoint + range) ----------
        COSArray labArr = new COSArray();
        labArr.add(COSName.LAB);
        COSDictionary labDict = new COSDictionary();
        COSArray wpD50 = new COSArray();
        wpD50.add(new COSFloat(0.9642f));
        wpD50.add(new COSFloat(1.0f));
        wpD50.add(new COSFloat(0.8249f));
        labDict.setItem(COSName.WHITE_POINT, wpD50);
        COSArray labRange = new COSArray();
        labRange.add(new COSFloat(-128));
        labRange.add(new COSFloat(127));
        labRange.add(new COSFloat(-128));
        labRange.add(new COSFloat(127));
        labDict.setItem(COSName.RANGE, labRange);
        labArr.add(labDict);
        PDLab lab = new PDLab(labArr);
        emit("Lab", new float[] {0.0f, 0.0f, 0.0f}, lab);
        emit("Lab", new float[] {100.0f, 0.0f, 0.0f}, lab);
        emit("Lab", new float[] {50.0f, 80.0f, 0.0f}, lab);
        emit("Lab", new float[] {50.0f, 0.0f, -80.0f}, lab);
        emit("Lab", new float[] {75.0f, -40.0f, 40.0f}, lab);

        // ---------- Indexed (DeviceRGB base, 4-entry palette) ----------
        byte[] palette = new byte[] {
            (byte) 0, (byte) 0, (byte) 0, // index 0 = black
            (byte) 255, (byte) 0, (byte) 0, // index 1 = red
            (byte) 0, (byte) 255, (byte) 0, // index 2 = green
            (byte) 128, (byte) 128, (byte) 255 // index 3 = light blue
        };
        COSArray idxArr = new COSArray();
        idxArr.add(COSName.INDEXED);
        idxArr.add(COSName.DEVICERGB);
        idxArr.add(COSInteger.get(3));
        idxArr.add(new org.apache.pdfbox.cos.COSString(palette));
        PDIndexed indexed = (PDIndexed) PDColorSpace.create(idxArr);
        emit("Indexed", new float[] {0.0f}, indexed);
        emit("Indexed", new float[] {1.0f}, indexed);
        emit("Indexed", new float[] {2.0f}, indexed);
        emit("Indexed", new float[] {3.0f}, indexed);

        // ---------- Separation (DeviceCMYK alternate, Type-2 tint) ----------
        // tint t -> (0, t, t, 0) CMYK : ramp toward red.
        COSArray sepArr = new COSArray();
        sepArr.add(COSName.SEPARATION);
        sepArr.add(COSName.getPDFName("MySpot"));
        sepArr.add(COSName.DEVICECMYK);
        sepArr.add(type2(
            new float[] {0.0f, 0.0f, 0.0f, 0.0f},
            new float[] {0.0f, 1.0f, 1.0f, 0.0f},
            1.0f));
        PDSeparation sep = new PDSeparation(sepArr);
        emit("Separation", new float[] {0.0f}, sep);
        emit("Separation", new float[] {0.5f}, sep);
        emit("Separation", new float[] {1.0f}, sep);

        // ---------- Separation with Type-4 PostScript tint ----------
        // single tint -> DeviceGray g = 1 - tint (darken).
        COSStream psStream = new COSStream();
        psStream.setInt(COSName.FUNCTION_TYPE, 4);
        COSArray dom = new COSArray();
        dom.add(new COSFloat(0));
        dom.add(new COSFloat(1));
        psStream.setItem(COSName.DOMAIN, dom);
        COSArray rng = new COSArray();
        rng.add(new COSFloat(0));
        rng.add(new COSFloat(1));
        psStream.setItem(COSName.RANGE, rng);
        String ps = "{ 1 exch sub }";
        java.io.OutputStream os = psStream.createOutputStream();
        os.write(ps.getBytes("US-ASCII"));
        os.close();
        COSArray sep4Arr = new COSArray();
        sep4Arr.add(COSName.SEPARATION);
        sep4Arr.add(COSName.getPDFName("PsSpot"));
        sep4Arr.add(COSName.DEVICEGRAY);
        sep4Arr.add(psStream);
        PDSeparation sep4 = new PDSeparation(sep4Arr);
        emit("SeparationPS", new float[] {0.0f}, sep4);
        emit("SeparationPS", new float[] {0.5f}, sep4);
        emit("SeparationPS", new float[] {1.0f}, sep4);

        // ---------- DeviceN (2 colorants, DeviceCMYK alternate) ----------
        // tint vector (a, b) -> CMYK (a, b, 0, 0)
        COSArray dnNames = new COSArray();
        dnNames.add(COSName.getPDFName("Spot1"));
        dnNames.add(COSName.getPDFName("Spot2"));
        COSArray dnArr = new COSArray();
        dnArr.add(COSName.DEVICEN);
        dnArr.add(dnNames);
        dnArr.add(COSName.DEVICECMYK);
        // Type-4 tint: 2 in -> 4 out: c=in0, m=in1, y=0, k=0
        COSStream dnStream = new COSStream();
        dnStream.setInt(COSName.FUNCTION_TYPE, 4);
        COSArray dnDom = new COSArray();
        dnDom.add(new COSFloat(0));
        dnDom.add(new COSFloat(1));
        dnDom.add(new COSFloat(0));
        dnDom.add(new COSFloat(1));
        dnStream.setItem(COSName.DOMAIN, dnDom);
        COSArray dnRng = new COSArray();
        for (int i = 0; i < 4; i++) {
            dnRng.add(new COSFloat(0));
            dnRng.add(new COSFloat(1));
        }
        dnStream.setItem(COSName.RANGE, dnRng);
        // stack in: a b ; want out: a b 0 0
        String dnps = "{ 0 0 }";
        java.io.OutputStream dnos = dnStream.createOutputStream();
        dnos.write(dnps.getBytes("US-ASCII"));
        dnos.close();
        dnArr.add(dnStream);
        PDDeviceN devicen = new PDDeviceN(dnArr);
        emit("DeviceN", new float[] {0.0f, 0.0f}, devicen);
        emit("DeviceN", new float[] {1.0f, 0.0f}, devicen);
        emit("DeviceN", new float[] {0.0f, 1.0f}, devicen);
        emit("DeviceN", new float[] {0.5f, 0.5f}, devicen);
    }
}
