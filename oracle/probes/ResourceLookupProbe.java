import java.io.PrintStream;
import java.util.List;
import java.util.TreeMap;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;

/**
 * Live oracle probe: build a /Resources dictionary in-memory exercising every
 * PDResources lookup category and dump, per key, the resolved object's runtime
 * class simple-name (plus presence flags and the well-known color-space name
 * shortcuts that resolve WITHOUT a resource entry).
 *
 * Usage: java -cp ... ResourceLookupProbe
 *
 * Output: a single JSON object, deterministic and repr-independent, that the
 * Python side reproduces with pypdfbox against the same resource graph.
 *
 * The resource dictionary is constructed entirely from COS primitives so the
 * probe needs no external fixture and the Python test can build the byte-for-
 * byte identical dictionary. Resolution order, COSName-vs-array dispatch,
 * Default* shortcuts, and getColorSpaceNames() are all driven through the same
 * PDResources public API both sides expose.
 */
public final class ResourceLookupProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        TreeMap<String, Object> root = new TreeMap<>();

        try (PDDocument doc = new PDDocument()) {
            PDResources res = new PDResources(buildResourceDict(), doc.getResourceCache());

            // ---- /Font ----
            // pypdfbox intentionally preserves a raw-COSDictionary surface for
            // *direct* font entries (typed PDFont only for indirect refs), so
            // comparing the resolved class would assert a documented
            // divergence. Instead report presence + the /Subtype both sides
            // agree on, which exercises the same lookup path faithfully.
            root.put("font_F0_present", res.getFont(COSName.getPDFName("F0")) != null);
            root.put("font_F0_subtype", fontSubtype(res, "F0"));
            root.put("font_missing_present",
                    res.getFont(COSName.getPDFName("Fx")) != null);

            // ---- /XObject ----
            root.put("xobject_Im0", xobjectClass(res, "Im0"));
            root.put("xobject_Fm0", xobjectClass(res, "Fm0"));
            root.put("xobject_missing", xobjectClass(res, "Imx"));
            root.put("is_image_Im0", res.isImageXObject(COSName.getPDFName("Im0")));
            root.put("is_image_Fm0", res.isImageXObject(COSName.getPDFName("Fm0")));

            // ---- /ColorSpace (named entries) ----
            root.put("cs_csIcc", csClass(res, "csIcc"));
            root.put("cs_csSep", csClass(res, "csSep"));
            root.put("cs_csCal", csClass(res, "csCal"));
            // ---- /ColorSpace well-known device shortcuts (no entry needed) ----
            root.put("cs_DeviceRGB", csClass(res, "DeviceRGB"));
            root.put("cs_DeviceGray", csClass(res, "DeviceGray"));
            root.put("cs_DeviceCMYK", csClass(res, "DeviceCMYK"));
            root.put("cs_Pattern", csClass(res, "Pattern"));
            // A non-device name with no /ColorSpace entry raises
            // MissingResourceException — capture the marker rather than a
            // class name so both sides compare the same failure mode.
            root.put("cs_missing", csResult(res, "csNope"));

            // ---- /ExtGState ----
            root.put("gs_gs0", extGStateClass(res, "gs0"));
            root.put("gs_missing", extGStateClass(res, "gsx"));

            // ---- /Shading ----
            root.put("sh_sh0", shadingClass(res, "sh0"));
            root.put("sh_missing", shadingClass(res, "shx"));

            // ---- /Pattern ----
            root.put("pat_p0", patternClass(res, "p0"));
            root.put("pat_p1", patternClass(res, "p1"));
            root.put("pat_missing", patternClass(res, "px"));

            // ---- /Properties ----
            root.put("prop_oc0", propertyListClass(res, "oc0"));
            root.put("prop_missing", propertyListClass(res, "Propx"));

            // ---- name listings (sorted for determinism) ----
            root.put("color_space_names", names(res.getColorSpaceNames()));
            root.put("xobject_names", names(res.getXObjectNames()));
            root.put("font_names", names(res.getFontNames()));
            root.put("ext_gstate_names", names(res.getExtGStateNames()));
            root.put("shading_names", names(res.getShadingNames()));
            root.put("pattern_names", names(res.getPatternNames()));
            root.put("property_names", names(res.getPropertiesNames()));
        }

        out.print(jsonify(root));
    }

    private static COSDictionary buildResourceDict() {
        COSDictionary r = new COSDictionary();

        // /Font/F0 — minimal Type1 Helvetica.
        COSDictionary font = new COSDictionary();
        font.setItem(COSName.TYPE, COSName.FONT);
        font.setItem(COSName.SUBTYPE, COSName.getPDFName("Type1"));
        font.setItem(COSName.BASE_FONT, COSName.getPDFName("Helvetica"));
        COSDictionary fonts = new COSDictionary();
        fonts.setItem(COSName.getPDFName("F0"), font);
        r.setItem(COSName.FONT, fonts);

        // /XObject — one image, one form.
        COSStream img = new COSStream();
        img.setItem(COSName.TYPE, COSName.XOBJECT);
        img.setItem(COSName.SUBTYPE, COSName.IMAGE);
        img.setInt(COSName.WIDTH, 1);
        img.setInt(COSName.HEIGHT, 1);
        img.setInt(COSName.BITS_PER_COMPONENT, 8);
        img.setItem(COSName.COLORSPACE, COSName.DEVICEGRAY);
        COSStream form = new COSStream();
        form.setItem(COSName.TYPE, COSName.XOBJECT);
        form.setItem(COSName.SUBTYPE, COSName.FORM);
        COSArray bbox = new COSArray();
        bbox.add(org.apache.pdfbox.cos.COSInteger.ZERO);
        bbox.add(org.apache.pdfbox.cos.COSInteger.ZERO);
        bbox.add(org.apache.pdfbox.cos.COSInteger.get(10));
        bbox.add(org.apache.pdfbox.cos.COSInteger.get(10));
        form.setItem(COSName.BBOX, bbox);
        COSDictionary xobjects = new COSDictionary();
        xobjects.setItem(COSName.getPDFName("Im0"), img);
        xobjects.setItem(COSName.getPDFName("Fm0"), form);
        r.setItem(COSName.XOBJECT, xobjects);

        // /ColorSpace — ICCBased (array), Separation (array), CalRGB (array).
        COSDictionary colorSpaces = new COSDictionary();
        // ICCBased: [/ICCBased <stream>]
        COSStream iccStream = new COSStream();
        iccStream.setInt(COSName.N, 3);
        COSArray icc = new COSArray();
        icc.add(COSName.getPDFName("ICCBased"));
        icc.add(iccStream);
        colorSpaces.setItem(COSName.getPDFName("csIcc"), icc);
        // Separation: [/Separation /Name /DeviceRGB <fn>]
        COSArray sep = new COSArray();
        sep.add(COSName.getPDFName("Separation"));
        sep.add(COSName.getPDFName("Spot"));
        sep.add(COSName.DEVICERGB);
        COSDictionary fn = new COSDictionary();
        fn.setInt(COSName.FUNCTION_TYPE, 2);
        COSArray domain = new COSArray();
        domain.add(org.apache.pdfbox.cos.COSInteger.ZERO);
        domain.add(org.apache.pdfbox.cos.COSInteger.get(1));
        fn.setItem(COSName.DOMAIN, domain);
        fn.setItem(COSName.getPDFName("N"), org.apache.pdfbox.cos.COSInteger.get(1));
        sep.add(fn);
        colorSpaces.setItem(COSName.getPDFName("csSep"), sep);
        // CalRGB: [/CalRGB <dict>]
        COSArray cal = new COSArray();
        cal.add(COSName.getPDFName("CalRGB"));
        cal.add(new COSDictionary());
        colorSpaces.setItem(COSName.getPDFName("csCal"), cal);
        r.setItem(COSName.COLORSPACE, colorSpaces);

        // /ExtGState
        COSDictionary gs = new COSDictionary();
        gs.setItem(COSName.TYPE, COSName.EXT_G_STATE);
        gs.setFloat(COSName.CA, 0.5f);
        COSDictionary extGStates = new COSDictionary();
        extGStates.setItem(COSName.getPDFName("gs0"), gs);
        r.setItem(COSName.EXT_G_STATE, extGStates);

        // /Shading — axial (type 2).
        COSDictionary shading = new COSDictionary();
        shading.setInt(COSName.SHADING_TYPE, 2);
        shading.setItem(COSName.COLORSPACE, COSName.DEVICERGB);
        COSArray coords = new COSArray();
        coords.add(org.apache.pdfbox.cos.COSInteger.ZERO);
        coords.add(org.apache.pdfbox.cos.COSInteger.ZERO);
        coords.add(org.apache.pdfbox.cos.COSInteger.get(1));
        coords.add(org.apache.pdfbox.cos.COSInteger.ZERO);
        shading.setItem(COSName.COORDS, coords);
        COSDictionary shadings = new COSDictionary();
        shadings.setItem(COSName.getPDFName("sh0"), shading);
        r.setItem(COSName.SHADING, shadings);

        // /Pattern — tiling (type 1, a stream) and shading (type 2, a dict).
        COSStream tiling = new COSStream();
        tiling.setItem(COSName.TYPE, COSName.PATTERN);
        tiling.setInt(COSName.PATTERN_TYPE, 1);
        tiling.setInt(COSName.PAINT_TYPE, 1);
        tiling.setInt(COSName.TILING_TYPE, 1);
        tiling.setItem(COSName.BBOX, bbox);
        tiling.setFloat(COSName.X_STEP, 10f);
        tiling.setFloat(COSName.Y_STEP, 10f);
        tiling.setItem(COSName.RESOURCES, new COSDictionary());
        COSDictionary shPattern = new COSDictionary();
        shPattern.setItem(COSName.TYPE, COSName.PATTERN);
        shPattern.setInt(COSName.PATTERN_TYPE, 2);
        shPattern.setItem(COSName.SHADING, shading);
        COSDictionary patterns = new COSDictionary();
        patterns.setItem(COSName.getPDFName("p0"), tiling);
        patterns.setItem(COSName.getPDFName("p1"), shPattern);
        r.setItem(COSName.PATTERN, patterns);

        // /Properties — an optional-content group.
        COSDictionary ocg = new COSDictionary();
        ocg.setItem(COSName.TYPE, COSName.OCG);
        ocg.setString(COSName.NAME, "layer0");
        COSDictionary props = new COSDictionary();
        props.setItem(COSName.getPDFName("oc0"), ocg);
        r.setItem(COSName.PROPERTIES, props);

        return r;
    }

    private static String fontSubtype(PDResources res, String name) throws Exception {
        org.apache.pdfbox.pdmodel.font.PDFont f =
                res.getFont(COSName.getPDFName(name));
        return f == null ? "NULL" : f.getCOSObject().getNameAsString(COSName.SUBTYPE);
    }

    private static String xobjectClass(PDResources res, String name) throws Exception {
        Object x = res.getXObject(COSName.getPDFName(name));
        return x == null ? "NULL" : x.getClass().getSimpleName();
    }

    private static String csClass(PDResources res, String name) throws Exception {
        PDColorSpace cs = res.getColorSpace(COSName.getPDFName(name));
        return cs == null ? "NULL" : cs.getClass().getSimpleName();
    }

    private static String csResult(PDResources res, String name) {
        try {
            PDColorSpace cs = res.getColorSpace(COSName.getPDFName(name));
            return cs == null ? "NULL" : cs.getClass().getSimpleName();
        } catch (org.apache.pdfbox.pdmodel.MissingResourceException e) {
            return "THROW:" + e.getMessage();
        } catch (Exception e) {
            return "THROW:" + e.getClass().getSimpleName();
        }
    }

    private static String extGStateClass(PDResources res, String name) {
        PDExtendedGraphicsState gs = res.getExtGState(COSName.getPDFName(name));
        return gs == null ? "NULL" : gs.getClass().getSimpleName();
    }

    private static String shadingClass(PDResources res, String name) throws Exception {
        Object sh = res.getShading(COSName.getPDFName(name));
        return sh == null ? "NULL" : sh.getClass().getSimpleName();
    }

    private static String patternClass(PDResources res, String name) throws Exception {
        Object p = res.getPattern(COSName.getPDFName(name));
        return p == null ? "NULL" : p.getClass().getSimpleName();
    }

    private static String propertyListClass(PDResources res, String name) {
        Object p = res.getProperties(COSName.getPDFName(name));
        return p == null ? "NULL" : p.getClass().getSimpleName();
    }

    private static java.util.List<String> names(Iterable<COSName> in) {
        java.util.TreeSet<String> set = new java.util.TreeSet<>();
        for (COSName n : in) {
            set.add(n.getName());
        }
        return new java.util.ArrayList<>(set);
    }

    // --- minimal JSON emitter (TreeMap / List / String / Boolean only) ---

    private static String jsonify(Object value) {
        StringBuilder sb = new StringBuilder();
        emit(sb, value);
        return sb.toString();
    }

    private static void emit(StringBuilder sb, Object value) {
        if (value == null) {
            sb.append("null");
        } else if (value instanceof java.util.Map<?, ?> map) {
            sb.append("{");
            boolean first = true;
            for (java.util.Map.Entry<?, ?> entry : map.entrySet()) {
                if (!first) {
                    sb.append(",");
                }
                first = false;
                emitString(sb, String.valueOf(entry.getKey()));
                sb.append(":");
                emit(sb, entry.getValue());
            }
            sb.append("}");
        } else if (value instanceof List<?> list) {
            sb.append("[");
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) {
                    sb.append(",");
                }
                emit(sb, list.get(i));
            }
            sb.append("]");
        } else if (value instanceof Boolean) {
            sb.append(value.toString());
        } else {
            emitString(sb, value.toString());
        }
    }

    private static void emitString(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
    }
}
