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
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;
import org.apache.pdfbox.pdmodel.graphics.form.PDTransparencyGroupAttributes;
import org.apache.pdfbox.util.Matrix;

/** Malformed PDFormXObject dictionary accessor oracle for wave 1521. */
public final class FormXObjectDictionaryFuzzProbe {
    private static final String[] CASE_IDS = {
        "base",
        "ft-i", "ft-f", "ft-w", "ft-z", "ft-ii", "ft-iz",
        "bb-v", "bb-s", "bb-n", "bb-w", "bb-z", "bb-ia", "bb-in", "bb-iz",
        "mx-v", "mx-s", "mx-n", "mx-w", "mx-z", "mx-ia", "mx-in", "mx-iz",
        "rs-v", "rs-w", "rs-z", "rs-id", "rs-iz",
        "gr-v", "gr-w", "gr-z", "gr-id", "gr-iz",
        "sp-i", "sp-f", "sp-w", "sp-z", "sp-ii", "sp-iz",
        "s1-i", "s1-f", "s1-w", "s1-z", "s1-ii", "s1-iz", "s1-both",
        "set", "clear"
    };

    private static final COSName TAG = COSName.getPDFName("Tag");
    private static final COSName STRUCT_PARENT = COSName.getPDFName("StructParent");

    private FormXObjectDictionaryFuzzProbe() {}

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

    private static COSDictionary tagged(String value) {
        COSDictionary dictionary = new COSDictionary();
        dictionary.setName(TAG, value);
        return dictionary;
    }

    private static PDFormXObject build(String caseId) {
        COSStream stream = new COSStream();
        COSArray array;
        switch (caseId) {
            case "base":
                break;
            case "ft-i":
                stream.setItem(COSName.FORMTYPE, COSInteger.get(7));
                break;
            case "ft-f":
                stream.setItem(COSName.FORMTYPE, new COSFloat(7.75f));
                break;
            case "ft-w":
                stream.setItem(COSName.FORMTYPE, COSName.getPDFName("Bad"));
                break;
            case "ft-z":
                stream.setItem(COSName.FORMTYPE, COSNull.NULL);
                break;
            case "ft-ii":
                stream.setItem(COSName.FORMTYPE, indirect(COSInteger.get(8)));
                break;
            case "ft-iz":
                stream.setItem(COSName.FORMTYPE, indirect(null));
                break;
            case "bb-v":
                stream.setItem(COSName.BBOX, numbers(4, 3, 1, 2));
                break;
            case "bb-s":
                stream.setItem(COSName.BBOX, numbers(1, 2, 3));
                break;
            case "bb-n":
                array = numbers(1, 2, 3, 4);
                array.set(2, COSName.getPDFName("Bad"));
                stream.setItem(COSName.BBOX, array);
                break;
            case "bb-w":
                stream.setItem(COSName.BBOX, COSName.getPDFName("Bad"));
                break;
            case "bb-z":
                stream.setItem(COSName.BBOX, COSNull.NULL);
                break;
            case "bb-ia":
                stream.setItem(COSName.BBOX, indirect(numbers(0, 1, 2, 3)));
                break;
            case "bb-in":
                array = numbers(0, 1, 2, 3);
                array.set(2, indirect(COSInteger.get(9)));
                stream.setItem(COSName.BBOX, array);
                break;
            case "bb-iz":
                stream.setItem(COSName.BBOX, indirect(null));
                break;
            case "mx-v":
                stream.setItem(COSName.MATRIX, numbers(2, 0, 0, 3, 4, 5));
                break;
            case "mx-s":
                stream.setItem(COSName.MATRIX, numbers(2, 0, 0, 3, 4));
                break;
            case "mx-n":
                array = numbers(2, 0, 0, 3, 4, 5);
                array.set(3, COSName.getPDFName("Bad"));
                stream.setItem(COSName.MATRIX, array);
                break;
            case "mx-w":
                stream.setItem(COSName.MATRIX, COSInteger.ONE);
                break;
            case "mx-z":
                stream.setItem(COSName.MATRIX, COSNull.NULL);
                break;
            case "mx-ia":
                stream.setItem(COSName.MATRIX, indirect(numbers(2, 0, 0, 3, 4, 5)));
                break;
            case "mx-in":
                array = numbers(2, 0, 0, 3, 4, 5);
                array.set(4, indirect(new COSFloat(9)));
                stream.setItem(COSName.MATRIX, array);
                break;
            case "mx-iz":
                stream.setItem(COSName.MATRIX, indirect(null));
                break;
            case "rs-v":
                stream.setItem(COSName.RESOURCES, tagged("R"));
                break;
            case "rs-w":
                stream.setItem(COSName.RESOURCES, COSInteger.ONE);
                break;
            case "rs-z":
                stream.setItem(COSName.RESOURCES, COSNull.NULL);
                break;
            case "rs-id":
                stream.setItem(COSName.RESOURCES, indirect(tagged("R")));
                break;
            case "rs-iz":
                stream.setItem(COSName.RESOURCES, indirect(null));
                break;
            case "gr-v":
                stream.setItem(COSName.GROUP, tagged("G"));
                break;
            case "gr-w":
                stream.setItem(COSName.GROUP, COSInteger.ONE);
                break;
            case "gr-z":
                stream.setItem(COSName.GROUP, COSNull.NULL);
                break;
            case "gr-id":
                stream.setItem(COSName.GROUP, indirect(tagged("G")));
                break;
            case "gr-iz":
                stream.setItem(COSName.GROUP, indirect(null));
                break;
            case "sp-i":
                stream.setItem(COSName.STRUCT_PARENTS, COSInteger.get(11));
                break;
            case "sp-f":
                stream.setItem(COSName.STRUCT_PARENTS, new COSFloat(11.75f));
                break;
            case "sp-w":
                stream.setItem(COSName.STRUCT_PARENTS, COSName.getPDFName("Bad"));
                break;
            case "sp-z":
                stream.setItem(COSName.STRUCT_PARENTS, COSNull.NULL);
                break;
            case "sp-ii":
                stream.setItem(COSName.STRUCT_PARENTS, indirect(COSInteger.get(12)));
                break;
            case "sp-iz":
                stream.setItem(COSName.STRUCT_PARENTS, indirect(null));
                break;
            case "s1-i":
                stream.setItem(STRUCT_PARENT, COSInteger.get(21));
                break;
            case "s1-f":
                stream.setItem(STRUCT_PARENT, new COSFloat(21.75f));
                break;
            case "s1-w":
                stream.setItem(STRUCT_PARENT, COSName.getPDFName("Bad"));
                break;
            case "s1-z":
                stream.setItem(STRUCT_PARENT, COSNull.NULL);
                break;
            case "s1-ii":
                stream.setItem(STRUCT_PARENT, indirect(COSInteger.get(22)));
                break;
            case "s1-iz":
                stream.setItem(STRUCT_PARENT, indirect(null));
                break;
            case "s1-both":
                stream.setItem(STRUCT_PARENT, COSInteger.get(21));
                stream.setItem(COSName.STRUCT_PARENTS, COSInteger.get(31));
                break;
            case "set":
            case "clear":
                stream.setItem(COSName.FORMTYPE, COSName.getPDFName("Bad"));
                stream.setItem(COSName.BBOX, COSName.getPDFName("Bad"));
                stream.setItem(COSName.MATRIX, COSName.getPDFName("Bad"));
                stream.setItem(COSName.RESOURCES, COSName.getPDFName("Bad"));
                stream.setItem(COSName.GROUP, COSName.getPDFName("Bad"));
                stream.setItem(COSName.STRUCT_PARENTS, COSName.getPDFName("Bad"));
                break;
            default:
                throw new IllegalArgumentException(caseId);
        }
        PDFormXObject form = new PDFormXObject(stream);
        if (caseId.equals("set") || caseId.equals("clear")) {
            form.setFormType(6);
            form.setBBox(new PDRectangle(1, 2, 3, 4));
            form.setMatrix(new AffineTransform(2, 0, 0, 3, 4, 5));
            form.setResources(new PDResources(tagged("R")));
            form.setGroup(new PDTransparencyGroupAttributes(tagged("G")));
            form.setStructParents(14);
            if (caseId.equals("clear")) {
                form.setBBox(null);
                form.setResources(null);
                form.setGroup(null);
            }
        }
        return form;
    }

    private static String number(float value) {
        if (value == (long) value) {
            return Long.toString((long) value);
        }
        return String.format(Locale.ROOT, "%s", value);
    }

    private static String bbox(PDFormXObject form) {
        try {
            PDRectangle value = form.getBBox();
            if (value == null) {
                return "none";
            }
            return String.join(
                    ",",
                    number(value.getLowerLeftX()),
                    number(value.getLowerLeftY()),
                    number(value.getUpperRightX()),
                    number(value.getUpperRightY()));
        } catch (RuntimeException exception) {
            return "err";
        }
    }

    private static String matrix(PDFormXObject form) {
        try {
            Matrix value = form.getMatrix();
            return String.join(
                    ",",
                    number(value.getScaleX()),
                    number(value.getShearY()),
                    number(value.getShearX()),
                    number(value.getScaleY()),
                    number(value.getTranslateX()),
                    number(value.getTranslateY()));
        } catch (RuntimeException exception) {
            return "err";
        }
    }

    private static String resources(PDFormXObject form) {
        try {
            PDResources value = form.getResources();
            if (value == null) {
                return "none";
            }
            String tag = value.getCOSObject().getNameAsString(TAG);
            return tag == null ? "empty" : tag;
        } catch (RuntimeException exception) {
            return "err";
        }
    }

    private static String group(PDFormXObject form) {
        try {
            PDTransparencyGroupAttributes value = form.getGroup();
            if (value == null) {
                return "none";
            }
            String tag = value.getCOSObject().getNameAsString(TAG);
            return tag == null ? "dict" : tag;
        } catch (RuntimeException exception) {
            return "err";
        }
    }

    private static String raw(COSDictionary dictionary, COSName key) {
        COSBase value = dictionary.getItem(key);
        if (value == null) {
            return "absent";
        }
        if (value instanceof COSObject) {
            return "indirect";
        }
        if (value instanceof COSArray) {
            COSArray array = (COSArray) value;
            StringBuilder result = new StringBuilder("array");
            for (int index = 0; index < array.size(); index++) {
                result.append(':').append(array.get(index).getClass().getSimpleName());
            }
            return result.toString();
        }
        return value.getClass().getSimpleName();
    }

    private static String project(String caseId) {
        PDFormXObject form = build(caseId);
        COSStream stream = form.getCOSObject();
        return "CASE " + caseId
                + " form=" + form.getFormType()
                + " bbox=" + bbox(form)
                + " matrix=" + matrix(form)
                + " resources=" + resources(form)
                + " group=" + group(form)
                + " struct=" + form.getStructParents()
                + " raw=" + String.join(
                        ",",
                        raw(stream, COSName.FORMTYPE),
                        raw(stream, COSName.BBOX),
                        raw(stream, COSName.MATRIX),
                        raw(stream, COSName.RESOURCES),
                        raw(stream, COSName.GROUP),
                        raw(stream, COSName.STRUCT_PARENTS),
                        raw(stream, STRUCT_PARENT));
    }

    public static void main(String[] args) {
        for (String caseId : CASE_IDS) {
            System.out.println(project(caseId));
        }
    }
}
