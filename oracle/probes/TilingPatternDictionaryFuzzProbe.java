import java.awt.geom.AffineTransform;
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
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.pattern.PDTilingPattern;

/** Direct malformed dictionary accessor oracle for PDTilingPattern. */
public final class TilingPatternDictionaryFuzzProbe {
    private static final COSName PAINT_TYPE = COSName.getPDFName("PaintType");
    private static final COSName TILING_TYPE = COSName.getPDFName("TilingType");
    private static final COSName BBOX = COSName.getPDFName("BBox");
    private static final COSName X_STEP = COSName.getPDFName("XStep");
    private static final COSName Y_STEP = COSName.getPDFName("YStep");
    private static final COSName MATRIX = COSName.getPDFName("Matrix");
    private static final COSName RESOURCES = COSName.getPDFName("Resources");

    private TilingPatternDictionaryFuzzProbe() {}

    private static COSObject indirect(COSBase value) {
        return new COSObject(value);
    }

    private static COSArray array(COSBase... values) {
        COSArray array = new COSArray();
        for (COSBase value : values) {
            array.add(value);
        }
        return array;
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

    private static String bbox(PDTilingPattern pattern) {
        try {
            PDRectangle value = pattern.getBBox();
            if (value == null) {
                return "none";
            }
            return bits(value.getLowerLeftX()) + "," + bits(value.getLowerLeftY())
                    + "," + bits(value.getUpperRightX()) + ","
                    + bits(value.getUpperRightY());
        } catch (Exception exception) {
            return "ERR:" + exception.getClass().getSimpleName();
        }
    }

    private static String matrix(PDTilingPattern pattern) {
        try {
            float[][] value = pattern.getMatrix().getValues();
            return bits(value[0][0]) + "," + bits(value[0][1]) + ","
                    + bits(value[1][0]) + "," + bits(value[1][1]) + ","
                    + bits(value[2][0]) + "," + bits(value[2][1]);
        } catch (Exception exception) {
            return "ERR:" + exception.getClass().getSimpleName();
        }
    }

    private static String resources(PDTilingPattern pattern) {
        try {
            PDResources value = pattern.getResources();
            if (value == null) {
                return "none";
            }
            return value.getCOSObject() instanceof COSStream ? "stream" : "dict";
        } catch (Exception exception) {
            return "ERR:" + exception.getClass().getSimpleName();
        }
    }

    private static String raw(COSDictionary dictionary, COSName key) {
        COSBase value = dictionary.getItem(key);
        if (value == null) {
            return "absent";
        }
        if (value instanceof COSObject) {
            COSBase resolved = ((COSObject) value).getObject();
            return "indirect:" + (resolved == null ? "null" : resolved.getClass().getSimpleName());
        }
        return value.getClass().getSimpleName();
    }

    private static void emit(String name, COSDictionary dictionary) {
        PDTilingPattern pattern = new PDTilingPattern(dictionary);
        System.out.println(
                "CASE " + name
                        + " paint=" + pattern.getPaintType()
                        + " tiling=" + pattern.getTilingType()
                        + " bbox=" + bbox(pattern)
                        + " x=" + bits(pattern.getXStep())
                        + " y=" + bits(pattern.getYStep())
                        + " matrix=" + matrix(pattern)
                        + " resources=" + resources(pattern));
    }

    private static void emitValueCases(COSName key, String prefix) {
        COSBase[] values = {
            COSInteger.get(7),
            new COSFloat(7.75f),
            COSInteger.get(4294967297L),
            COSName.getPDFName("Bad"),
            COSNull.NULL,
            indirect(COSInteger.get(9)),
            indirect(null)
        };
        String[] ids = {"i", "f", "wide", "name", "null", "ii", "inull"};
        for (int index = 0; index < values.length; index++) {
            COSDictionary dictionary = new COSDictionary();
            dictionary.setItem(key, values[index]);
            emit(prefix + "-" + ids[index], dictionary);
        }
    }

    private static void emitArrayCases(COSName key, String prefix, boolean rectangle) {
        COSBase[] values = {
            numbers(),
            numbers(1, 2),
            numbers(4, 3, 2, 1),
            numbers(1, 2, 3, 4, 5, 6, 7),
            array(COSInteger.ONE, COSName.getPDFName("Bad"), COSNull.NULL,
                    new COSFloat(4.5f), COSInteger.get(5), COSInteger.get(6)),
            indirect(rectangle ? numbers(4, 3, 2, 1) : numbers(1, 2, 3, 4, 5, 6)),
            indirect(COSName.getPDFName("Bad")),
            indirect(null),
            array(indirect(COSInteger.ONE), indirect(new COSFloat(2.5f)),
                    COSInteger.get(3), COSInteger.get(4), COSInteger.get(5), COSInteger.get(6)),
            rectangle
                    ? array(new COSFloat(1.0e20f), new COSFloat(-1.0e20f),
                            new COSFloat(-1.0e20f), new COSFloat(1.0e20f))
                    : array(COSInteger.get(16777217), COSInteger.ZERO, COSInteger.ZERO,
                            COSInteger.ONE, COSInteger.get(16777217), COSInteger.get(-16777217))
        };
        String[] ids = {
            "empty", "short", "full", "long", "mixed", "ind", "iname", "inull", "ielems",
            "overflow"
        };
        for (int index = 0; index < values.length; index++) {
            COSDictionary dictionary = new COSDictionary();
            dictionary.setItem(key, values[index]);
            emit(prefix + "-" + ids[index], dictionary);
        }
    }

    private static void emitResourceCases() {
        COSBase[] values = {
            new COSDictionary(),
            new COSStream(),
            COSName.getPDFName("Bad"),
            COSNull.NULL,
            indirect(new COSDictionary()),
            indirect(new COSStream()),
            indirect(null)
        };
        String[] ids = {"dict", "stream", "name", "null", "idict", "istream", "inull"};
        for (int index = 0; index < values.length; index++) {
            COSDictionary dictionary = new COSDictionary();
            dictionary.setItem(RESOURCES, values[index]);
            emit("res-" + ids[index], dictionary);
        }
    }

    private static void emitSetterCases() {
        PDTilingPattern pattern = new PDTilingPattern(new COSStream());
        pattern.setPaintType(2);
        pattern.setTilingType(3);
        pattern.setXStep(7.25f);
        pattern.setYStep(-8.5f);
        pattern.setBBox(new PDRectangle(4, 3, 2, 1));
        pattern.setMatrix(new AffineTransform(1.5, 2.5, 3.5, 4.5, 5.5, 6.5));
        pattern.setResources(new PDResources());
        COSDictionary dictionary = pattern.getCOSObject();
        System.out.println(
                "SET values paint=" + raw(dictionary, PAINT_TYPE)
                        + " tiling=" + raw(dictionary, TILING_TYPE)
                        + " bbox=" + raw(dictionary, BBOX)
                        + " x=" + raw(dictionary, X_STEP)
                        + " y=" + raw(dictionary, Y_STEP)
                        + " matrix=" + raw(dictionary, MATRIX)
                        + " resources=" + raw(dictionary, RESOURCES)
                        + " projection=" + bbox(pattern) + ";" + matrix(pattern));

        pattern.setBBox(null);
        String matrixAction;
        try {
            pattern.setMatrix(null);
            matrixAction = "ok";
        } catch (Exception exception) {
            matrixAction = "ERR:" + exception.getClass().getSimpleName();
        }
        pattern.setResources(null);
        System.out.println(
                "SET clear action=" + matrixAction
                        + " bbox=" + raw(dictionary, BBOX)
                        + " matrix=" + raw(dictionary, MATRIX)
                        + " resources=" + raw(dictionary, RESOURCES));
    }

    public static void main(String[] args) {
        emit("default", new PDTilingPattern().getCOSObject());
        emit("empty", new COSDictionary());
        emitValueCases(PAINT_TYPE, "paint");
        emitValueCases(TILING_TYPE, "tiling");
        emitValueCases(X_STEP, "x");
        emitValueCases(Y_STEP, "y");

        COSDictionary wrong = new COSDictionary();
        wrong.setItem(BBOX, COSName.getPDFName("Bad"));
        emit("bbox-name", wrong);
        wrong = new COSDictionary();
        wrong.setItem(BBOX, COSNull.NULL);
        emit("bbox-null", wrong);
        emitArrayCases(BBOX, "bbox", true);

        wrong = new COSDictionary();
        wrong.setItem(MATRIX, COSName.getPDFName("Bad"));
        emit("matrix-name", wrong);
        wrong = new COSDictionary();
        wrong.setItem(MATRIX, COSNull.NULL);
        emit("matrix-null", wrong);
        emitArrayCases(MATRIX, "matrix", false);

        emitResourceCases();
        emitSetterCases();
    }
}
