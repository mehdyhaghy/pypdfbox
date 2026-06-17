import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.graphics.pattern.PDAbstractPattern;
import org.apache.pdfbox.pdmodel.graphics.pattern.PDShadingPattern;
import org.apache.pdfbox.pdmodel.graphics.pattern.PDTilingPattern;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShading;

/**
 * Differential oracle for the {@code PDAbstractPattern.create} dispatcher and
 * the subclass surface it produces. Drives {@code create} over malformed
 * {@code /PatternType} (tiling/shading/missing/garbage/non-int), then projects
 * the resulting wrapper's class plus its key accessors so a Python port can
 * pin both-sides parity. Complements TilingPatternDictionaryFuzzProbe (which
 * fuzzes a *pre-typed* PDTilingPattern's accessors); this probe fuzzes the
 * dispatch decision itself plus shading-pattern /Shading + /ExtGState.
 */
public final class PatternFuzzProbe {
    private static final COSName PATTERN_TYPE = COSName.getPDFName("PatternType");
    private static final COSName PAINT_TYPE = COSName.getPDFName("PaintType");
    private static final COSName TILING_TYPE = COSName.getPDFName("TilingType");
    private static final COSName BBOX = COSName.getPDFName("BBox");
    private static final COSName X_STEP = COSName.getPDFName("XStep");
    private static final COSName Y_STEP = COSName.getPDFName("YStep");
    private static final COSName MATRIX = COSName.getPDFName("Matrix");
    private static final COSName RESOURCES = COSName.getPDFName("Resources");
    private static final COSName SHADING = COSName.getPDFName("Shading");
    private static final COSName EXT_G_STATE = COSName.getPDFName("ExtGState");

    private PatternFuzzProbe() {}

    private static COSObject indirect(COSBase value) {
        return new COSObject(value);
    }

    private static COSArray numbers(float... values) {
        COSArray array = new COSArray();
        for (float value : values) {
            array.add(new COSFloat(value));
        }
        return array;
    }

    private static String bits(float value) {
        return String.format(Locale.ROOT, "%08x", Float.floatToIntBits(value));
    }

    private static String matrix(PDAbstractPattern pattern) {
        try {
            float[][] value = pattern.getMatrix().getValues();
            return bits(value[0][0]) + "," + bits(value[0][1]) + ","
                    + bits(value[1][0]) + "," + bits(value[1][1]) + ","
                    + bits(value[2][0]) + "," + bits(value[2][1]);
        } catch (Exception exception) {
            return "ERR:" + exception.getClass().getSimpleName();
        }
    }

    private static String shadingExtState(PDShadingPattern pattern) {
        // PDFBox 3.0.7 only exposes getExtendedGraphicsState() on the shading
        // subclass; PDTilingPattern carries no /ExtGState accessor upstream.
        try {
            return pattern.getExtendedGraphicsState() == null ? "none" : "present";
        } catch (Exception exception) {
            return "ERR:" + exception.getClass().getSimpleName();
        }
    }

    private static String tilingProjection(PDTilingPattern pattern) {
        String bbox;
        try {
            bbox = pattern.getBBox() == null ? "none" : "rect";
        } catch (Exception exception) {
            bbox = "ERR:" + exception.getClass().getSimpleName();
        }
        String resources;
        try {
            resources = pattern.getResources() == null ? "none" : "present";
        } catch (Exception exception) {
            resources = "ERR:" + exception.getClass().getSimpleName();
        }
        return "paint=" + pattern.getPaintType()
                + " ptype=" + pattern.getPatternType()
                + " tiling=" + pattern.getTilingType()
                + " bbox=" + bbox
                + " x=" + bits(pattern.getXStep())
                + " y=" + bits(pattern.getYStep())
                + " matrix=" + matrix(pattern)
                + " resources=" + resources;
    }

    private static String shadingProjection(PDShadingPattern pattern) {
        String shading;
        try {
            PDShading value = pattern.getShading();
            shading = value == null ? "none" : ("type" + value.getShadingType());
        } catch (Exception exception) {
            shading = "ERR:" + exception.getClass().getSimpleName();
        }
        return "ptype=" + pattern.getPatternType()
                + " shading=" + shading
                + " matrix=" + matrix(pattern)
                + " ext=" + shadingExtState(pattern);
    }

    private static void dispatch(String name, COSDictionary dictionary) {
        String line;
        try {
            PDAbstractPattern pattern = PDAbstractPattern.create(dictionary, null);
            if (pattern == null) {
                line = "null";
            } else if (pattern instanceof PDTilingPattern) {
                line = "tiling " + tilingProjection((PDTilingPattern) pattern);
            } else if (pattern instanceof PDShadingPattern) {
                line = "shading " + shadingProjection((PDShadingPattern) pattern);
            } else {
                line = "other:" + pattern.getClass().getSimpleName();
            }
        } catch (Exception exception) {
            line = "ERR:" + exception.getClass().getSimpleName();
        }
        System.out.println("CASE " + name + " " + line);
    }

    private static COSDictionary withType(COSBase patternType) {
        COSDictionary dictionary = new COSDictionary();
        if (patternType != null) {
            dictionary.setItem(PATTERN_TYPE, patternType);
        }
        return dictionary;
    }

    private static COSDictionary minimalShading() {
        COSDictionary shading = new COSDictionary();
        shading.setItem(COSName.SHADING_TYPE, COSInteger.get(2));
        shading.setItem(COSName.COLORSPACE, COSName.DEVICERGB);
        return shading;
    }

    public static void main(String[] args) {
        // ----- /PatternType dispatch -----
        dispatch("ptype-missing", withType(null));
        dispatch("ptype-1", withType(COSInteger.get(1)));
        dispatch("ptype-2", withType(COSInteger.get(2)));
        dispatch("ptype-0", withType(COSInteger.ZERO));
        dispatch("ptype-3", withType(COSInteger.get(3)));
        dispatch("ptype-neg", withType(COSInteger.get(-1)));
        dispatch("ptype-wide", withType(COSInteger.get(4294967297L)));
        dispatch("ptype-float1", withType(new COSFloat(1.0f)));
        dispatch("ptype-float1p9", withType(new COSFloat(1.9f)));
        dispatch("ptype-float2", withType(new COSFloat(2.4f)));
        dispatch("ptype-name", withType(COSName.getPDFName("Bad")));
        dispatch("ptype-null", withType(COSNull.NULL));
        dispatch("ptype-i1", withType(indirect(COSInteger.get(1))));
        dispatch("ptype-i2", withType(indirect(COSInteger.get(2))));
        dispatch("ptype-inull", withType(indirect(null)));

        // ----- tiling (type 1) body fuzz via dispatch -----
        COSDictionary t = withType(COSInteger.get(1));
        dispatch("tiling-bare", t);

        t = withType(COSInteger.get(1));
        t.setItem(PAINT_TYPE, new COSFloat(2.5f));
        dispatch("tiling-paint-float", t);

        t = withType(COSInteger.get(1));
        t.setItem(TILING_TYPE, COSName.getPDFName("Bad"));
        dispatch("tiling-tiling-name", t);

        t = withType(COSInteger.get(1));
        t.setItem(BBOX, numbers(4, 3, 2, 1));
        t.setItem(X_STEP, new COSFloat(10.0f));
        t.setItem(Y_STEP, new COSFloat(-20.0f));
        dispatch("tiling-bbox-full", t);

        t = withType(COSInteger.get(1));
        t.setItem(BBOX, numbers(1, 2));
        dispatch("tiling-bbox-short", t);

        t = withType(COSInteger.get(1));
        t.setItem(X_STEP, COSInteger.ZERO);
        t.setItem(Y_STEP, COSInteger.get(-5));
        dispatch("tiling-step-zeroneg", t);

        t = withType(COSInteger.get(1));
        t.setItem(MATRIX, numbers(1, 2, 3, 4, 5));
        dispatch("tiling-matrix-short", t);

        t = withType(COSInteger.get(1));
        t.setItem(RESOURCES, COSName.getPDFName("Bad"));
        dispatch("tiling-res-name", t);

        t = withType(COSInteger.get(1));
        t.setItem(RESOURCES, new COSDictionary());
        dispatch("tiling-res-dict", t);

        t = withType(COSInteger.get(1));
        t.setItem(EXT_G_STATE, new COSDictionary());
        dispatch("tiling-ext-dict", t);

        // ----- shading (type 2) body fuzz via dispatch -----
        COSDictionary s = withType(COSInteger.get(2));
        dispatch("shading-bare", s);

        s = withType(COSInteger.get(2));
        s.setItem(SHADING, minimalShading());
        dispatch("shading-dict", s);

        s = withType(COSInteger.get(2));
        COSStream shadingStream = new COSStream();
        shadingStream.setItem(COSName.SHADING_TYPE, COSInteger.get(4));
        shadingStream.setItem(COSName.COLORSPACE, COSName.DEVICERGB);
        s.setItem(SHADING, shadingStream);
        dispatch("shading-stream", s);

        s = withType(COSInteger.get(2));
        s.setItem(SHADING, COSName.getPDFName("Bad"));
        dispatch("shading-name", s);

        s = withType(COSInteger.get(2));
        s.setItem(SHADING, COSNull.NULL);
        dispatch("shading-null", s);

        s = withType(COSInteger.get(2));
        s.setItem(SHADING, indirect(minimalShading()));
        dispatch("shading-idict", s);

        s = withType(COSInteger.get(2));
        s.setItem(SHADING, minimalShading());
        s.setItem(MATRIX, numbers(2, 0, 0, 2, 5, 5));
        s.setItem(EXT_G_STATE, new COSDictionary());
        dispatch("shading-full", s);

        s = withType(COSInteger.get(2));
        s.setItem(SHADING, minimalShading());
        s.setItem(EXT_G_STATE, COSName.getPDFName("Bad"));
        dispatch("shading-ext-name", s);
    }
}
