import java.io.ByteArrayOutputStream;
import java.io.OutputStream;
import java.util.List;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.color.SetNonStrokingColor;
import org.apache.pdfbox.contentstream.operator.color.SetNonStrokingColorN;
import org.apache.pdfbox.contentstream.operator.color.SetNonStrokingColorSpace;
import org.apache.pdfbox.contentstream.operator.color.SetNonStrokingDeviceCMYKColor;
import org.apache.pdfbox.contentstream.operator.color.SetNonStrokingDeviceGrayColor;
import org.apache.pdfbox.contentstream.operator.color.SetNonStrokingDeviceRGBColor;
import org.apache.pdfbox.contentstream.operator.color.SetStrokingColor;
import org.apache.pdfbox.contentstream.operator.color.SetStrokingColorN;
import org.apache.pdfbox.contentstream.operator.color.SetStrokingColorSpace;
import org.apache.pdfbox.contentstream.operator.color.SetStrokingDeviceCMYKColor;
import org.apache.pdfbox.contentstream.operator.color.SetStrokingDeviceGrayColor;
import org.apache.pdfbox.contentstream.operator.color.SetStrokingDeviceRGBColor;
import org.apache.pdfbox.contentstream.operator.state.Restore;
import org.apache.pdfbox.contentstream.operator.state.Save;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;

/**
 * Live oracle probe for the engine-level colour-operator <em>state</em> +
 * colour-space resolution surface — complementary to
 * {@code SetColorOperandProbe} (which projects only the resulting {@link
 * PDColor}). This probe additionally projects the graphics-state's current
 * stroking / non-stroking <em>colour space name</em> after running each
 * content stream, so it catches the implicit colour-space switch performed
 * by the device operators {@code g}/{@code G}/{@code rg}/{@code RG}/
 * {@code k}/{@code K} (upstream sets the graphics-state colour space, then
 * the colour) as well as the {@code cs}/{@code CS} named-resource path.
 *
 * Fuzz angles (NOT already covered by SetColorOperandProbe):
 *   - device operators after a named colour space (implicit cs switch).
 *   - cs/CS with a device name vs a named resource vs missing vs unknown.
 *   - setting colour before setting a colour space (initial DeviceGray).
 *   - nested q/Q colour-state restore.
 *   - scn for a Separation / DeviceN with a component-count mismatch.
 *   - DefaultGray/DefaultRGB substitution via /Resources.
 *
 * Canonical signal per case (four lines):
 *   stroke=&lt;PDColor describe&gt;
 *   nonstroke=&lt;PDColor describe&gt;
 *   stroke_cs=&lt;name|null&gt;
 *   nonstroke_cs=&lt;name|null&gt;
 *
 * argv[0] = case name (see CASES below).
 */
public final class ColorOperatorFuzzProbe {

    static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Integer.toString((int) v);
        }
        return Float.toString(v);
    }

    static String describe(PDColor c) {
        if (c == null) {
            return "null";
        }
        StringBuilder sb = new StringBuilder();
        sb.append("comps[");
        float[] comps = c.getComponents();
        for (int i = 0; i < comps.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(fmt(comps[i]));
        }
        sb.append("] pattern=");
        COSName pn = c.getPatternName();
        sb.append(pn == null ? "null" : pn.getName());
        sb.append(" cs=");
        sb.append(c.getColorSpace() == null ? "null" : c.getColorSpace().getName());
        return sb.toString();
    }

    static String csName(PDColorSpace cs) {
        return cs == null ? "null" : cs.getName();
    }

    /** A separation colorspace: [ /Separation /Spot /DeviceCMYK <type2 fn> ]. */
    static COSArray separationCS() {
        COSDictionary fn = new COSDictionary();
        fn.setInt(COSName.FUNCTION_TYPE, 2);
        COSArray domain = new COSArray();
        domain.add(new COSFloat(0));
        domain.add(new COSFloat(1));
        fn.setItem(COSName.DOMAIN, domain);
        COSArray c0 = new COSArray();
        for (int i = 0; i < 4; i++) {
            c0.add(new COSFloat(0));
        }
        COSArray c1 = new COSArray();
        c1.add(new COSFloat(0));
        c1.add(new COSFloat(1));
        c1.add(new COSFloat(0));
        c1.add(new COSFloat(0));
        fn.setItem(COSName.getPDFName("C0"), c0);
        fn.setItem(COSName.getPDFName("C1"), c1);
        fn.setItem(COSName.N, new COSFloat(1));
        COSArray sep = new COSArray();
        sep.add(COSName.SEPARATION);
        sep.add(COSName.getPDFName("Spot"));
        sep.add(COSName.DEVICECMYK);
        sep.add(fn);
        return sep;
    }

    /** A DeviceN colorspace with 2 colorants over DeviceCMYK. */
    static COSArray deviceNCS() {
        COSDictionary fn = new COSDictionary();
        fn.setInt(COSName.FUNCTION_TYPE, 2);
        COSArray domain = new COSArray();
        domain.add(new COSFloat(0));
        domain.add(new COSFloat(1));
        fn.setItem(COSName.DOMAIN, domain);
        COSArray c0 = new COSArray();
        for (int i = 0; i < 4; i++) {
            c0.add(new COSFloat(0));
        }
        COSArray c1 = new COSArray();
        for (int i = 0; i < 4; i++) {
            c1.add(new COSFloat(1));
        }
        fn.setItem(COSName.getPDFName("C0"), c0);
        fn.setItem(COSName.getPDFName("C1"), c1);
        fn.setItem(COSName.N, new COSFloat(1));
        COSArray names = new COSArray();
        names.add(COSName.getPDFName("SpotA"));
        names.add(COSName.getPDFName("SpotB"));
        COSArray dn = new COSArray();
        dn.add(COSName.DEVICEN);
        dn.add(names);
        dn.add(COSName.DEVICECMYK);
        dn.add(fn);
        return dn;
    }

    static String contentFor(String which) {
        switch (which) {
            // ---- device operators set the implicit colour space ----
            case "g_only":
                return "0.5 g\n";
            case "rg_only":
                return "0.1 0.2 0.3 rg\n";
            case "k_only":
                return "0.1 0.2 0.3 0.4 k\n";
            case "G_RG_K":
                return "0.5 G 0.1 0.2 0.3 RG 0.1 0.2 0.3 0.4 K\n";
            // device op AFTER a named colour space -> must switch back.
            case "named_then_g":
                return "/CSRGB cs 0.5 g\n";
            case "named_then_G":
                return "/CSRGB CS 0.5 G\n";
            case "named_then_rg":
                return "/CSCMYK cs 0.1 0.2 0.3 rg\n";
            case "g_then_named_then_k":
                return "0.5 g /CSRGB cs 0.1 0.2 0.3 0.4 k\n";
            // ---- cs/CS resolution variants ----
            case "cs_device_name":
                return "/DeviceRGB cs 0.1 0.2 0.3 scn\n";
            case "CS_device_name":
                return "/DeviceCMYK CS 0.1 0.2 0.3 0.4 SCN\n";
            case "cs_missing_resource":
                return "/NotThere cs 0.1 0.2 0.3 scn\n";
            case "cs_unknown_inline":
                return "/Bogus cs 0.5 scn\n";
            case "cs_default_gray":
                // DeviceGray cs picks up /DefaultGray (a Separation here).
                return "/DeviceGray cs 0.7 scn\n";
            // ---- colour before colour space (initial DeviceGray) ----
            case "scn_before_cs":
                return "0.5 scn\n";
            case "sc_before_cs":
                return "0.5 sc\n";
            // ---- nested q/Q colour-state restore ----
            case "q_restore_device":
                return "0.1 0.2 0.3 rg q 0.9 g Q\n";
            case "q_restore_named":
                return "/CSRGB cs 0.1 0.2 0.3 scn q /CSCMYK cs 0.1 0.2 0.3 0.4 scn Q\n";
            case "q_nested_restore":
                return "0.2 g q 0.4 g q 0.6 g Q Q\n";
            // ---- Separation / DeviceN component counts ----
            case "sep_ok":
                return "/Sep cs 0.7 scn\n";
            case "sep_too_few":
                return "/Sep cs scn\n";
            case "sep_extra":
                return "/Sep cs 0.7 0.9 scn\n";
            case "devicen_ok":
                return "/DevN cs 0.3 0.6 scn\n";
            case "devicen_too_few":
                return "/DevN cs 0.3 scn\n";
            // ---- pattern colour space ----
            case "pattern_name_only":
                return "/Pattern cs /P1 scn\n";
            case "pattern_uncolored":
                return "/PatternU cs 0.5 /P1 scn\n";
            case "pattern_no_name":
                return "/Pattern cs scn\n";
            // ---- device op clamping is NOT done at sc time (raw kept) ----
            case "rg_out_of_range":
                return "1.5 -0.2 0.3 rg\n";
            case "g_out_of_range":
                return "2.0 g\n";
            // ---- mixed stroke + nonstroke independence ----
            case "stroke_rgb_nonstroke_gray":
                return "0.1 0.2 0.3 RG 0.5 g\n";
            // ---- device op with too few operands (skip) ----
            case "rg_too_few":
                return "0.1 0.2 rg\n";
            case "k_too_few":
                return "0.1 0.2 0.3 k\n";
            default:
                return "";
        }
    }

    public static void main(String[] argv) throws Exception {
        final String which = argv.length > 0 ? argv[0] : "g_only";
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            PDResources res = new PDResources();

            COSDictionary csDict = new COSDictionary();
            csDict.setItem(COSName.getPDFName("CSRGB"), COSName.DEVICERGB);
            csDict.setItem(COSName.getPDFName("CSCMYK"), COSName.DEVICECMYK);
            csDict.setItem(COSName.getPDFName("Sep"), separationCS());
            csDict.setItem(COSName.getPDFName("DevN"), deviceNCS());
            // /DefaultGray substitution: a Separation stands in for DeviceGray.
            csDict.setItem(COSName.getPDFName("DefaultGray"), separationCS());
            COSArray patU = new COSArray();
            patU.add(COSName.PATTERN);
            patU.add(COSName.DEVICEGRAY);
            csDict.setItem(COSName.getPDFName("PatternU"), patU);
            res.getCOSObject().setItem(COSName.COLORSPACE, csDict);

            COSDictionary patDict = new COSDictionary();
            COSStream tiling = doc.getDocument().createCOSStream();
            tiling.setItem(COSName.TYPE, COSName.PATTERN);
            tiling.setInt(COSName.PATTERN_TYPE, 1);
            tiling.setInt(COSName.PAINT_TYPE, 1);
            tiling.setInt(COSName.TILING_TYPE, 1);
            COSArray bbox = new COSArray();
            bbox.add(new COSFloat(0));
            bbox.add(new COSFloat(0));
            bbox.add(new COSFloat(1));
            bbox.add(new COSFloat(1));
            tiling.setItem(COSName.BBOX, bbox);
            tiling.setFloat(COSName.X_STEP, 1);
            tiling.setFloat(COSName.Y_STEP, 1);
            patDict.setItem(COSName.getPDFName("P1"),
                    org.apache.pdfbox.pdmodel.graphics.pattern.PDAbstractPattern
                            .create(tiling, null).getCOSObject());
            res.getCOSObject().setItem(COSName.PATTERN, patDict);

            byte[] content = contentFor(which).getBytes("US-ASCII");
            PDStream cs = new PDStream(doc);
            try (OutputStream os = cs.createOutputStream()) {
                os.write(content);
            }
            page.setContents(cs);
            page.setResources(res);

            final PDColor[] capturedColor = new PDColor[2];
            final PDColorSpace[] capturedCS = new PDColorSpace[2];
            PDFStreamEngine engine = new PDFStreamEngine() {
                @Override
                public void processOperator(Operator operator,
                        List<org.apache.pdfbox.cos.COSBase> operands)
                        throws java.io.IOException {
                    super.processOperator(operator, operands);
                    capturedColor[0] = getGraphicsState().getStrokingColor();
                    capturedColor[1] = getGraphicsState().getNonStrokingColor();
                    capturedCS[0] = getGraphicsState().getStrokingColorSpace();
                    capturedCS[1] = getGraphicsState().getNonStrokingColorSpace();
                }
            };
            engine.addOperator(new SetStrokingColor(engine));
            engine.addOperator(new SetNonStrokingColor(engine));
            engine.addOperator(new SetStrokingColorN(engine));
            engine.addOperator(new SetNonStrokingColorN(engine));
            engine.addOperator(new SetStrokingColorSpace(engine));
            engine.addOperator(new SetNonStrokingColorSpace(engine));
            engine.addOperator(new SetStrokingDeviceRGBColor(engine));
            engine.addOperator(new SetNonStrokingDeviceRGBColor(engine));
            engine.addOperator(new SetStrokingDeviceGrayColor(engine));
            engine.addOperator(new SetNonStrokingDeviceGrayColor(engine));
            engine.addOperator(new SetStrokingDeviceCMYKColor(engine));
            engine.addOperator(new SetNonStrokingDeviceCMYKColor(engine));
            engine.addOperator(new Save(engine));
            engine.addOperator(new Restore(engine));

            engine.processPage(page);

            System.out.println("stroke=" + describe(capturedColor[0]));
            System.out.println("nonstroke=" + describe(capturedColor[1]));
            System.out.println("stroke_cs=" + csName(capturedCS[0]));
            System.out.println("nonstroke_cs=" + csName(capturedCS[1]));
        }
    }
}
