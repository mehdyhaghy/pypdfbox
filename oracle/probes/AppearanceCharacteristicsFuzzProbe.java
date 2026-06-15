import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary;

/**
 * Direct malformed-input oracle for PDAppearanceCharacteristicsDictionary
 * (the /MK dictionary on widget annotations), PDFBox 3.0.7.
 */
public final class AppearanceCharacteristicsFuzzProbe {

    private static COSObject indirect(COSBase value) {
        return new COSObject(value);
    }

    private static String message(Exception exception) {
        String value = exception.getMessage();
        return value == null ? exception.getClass().getSimpleName() : value.replace(' ', '_');
    }

    private static String num(double value) {
        return value == Math.rint(value) ? Long.toString((long) value) : Double.toString(value);
    }

    private static String color(PDColor color) {
        if (color == null) {
            return "none";
        }
        StringBuilder sb = new StringBuilder();
        try {
            sb.append(color.getColorSpace().getName());
        } catch (Exception exception) {
            sb.append("ERR:").append(message(exception));
        }
        sb.append("[");
        try {
            float[] components = color.getComponents();
            List<String> parts = new ArrayList<>();
            for (float component : components) {
                parts.add(num(component));
            }
            sb.append(String.join(",", parts));
        } catch (Exception exception) {
            sb.append("ERR:").append(message(exception));
        }
        sb.append("]");
        return sb.toString();
    }

    private static String icon(PDFormXObject icon) {
        return icon == null ? "none" : "form";
    }

    private static String text(String value) {
        return value == null ? "none" : value.replace(' ', '_');
    }

    private static void emit(String name, PDAppearanceCharacteristicsDictionary mk) {
        StringBuilder sb = new StringBuilder("CASE " + name);
        try {
            sb.append(" rot=").append(mk.getRotation());
        } catch (Exception exception) {
            sb.append(" rot=ERR:").append(message(exception));
        }
        try {
            sb.append(" bc=").append(color(mk.getBorderColour()));
        } catch (Exception exception) {
            sb.append(" bc=ERR:").append(message(exception));
        }
        try {
            sb.append(" bg=").append(color(mk.getBackground()));
        } catch (Exception exception) {
            sb.append(" bg=ERR:").append(message(exception));
        }
        sb.append(" ca=").append(text(mk.getNormalCaption()));
        sb.append(" rc=").append(text(mk.getRolloverCaption()));
        sb.append(" ac=").append(text(mk.getAlternateCaption()));
        try {
            sb.append(" ni=").append(icon(mk.getNormalIcon()));
        } catch (Exception exception) {
            sb.append(" ni=ERR:").append(message(exception));
        }
        try {
            sb.append(" ri=").append(icon(mk.getRolloverIcon()));
        } catch (Exception exception) {
            sb.append(" ri=ERR:").append(message(exception));
        }
        try {
            sb.append(" ai=").append(icon(mk.getAlternateIcon()));
        } catch (Exception exception) {
            sb.append(" ai=ERR:").append(message(exception));
        }
        System.out.println(sb.toString());
    }

    private static PDAppearanceCharacteristicsDictionary mk(COSDictionary dictionary) {
        return new PDAppearanceCharacteristicsDictionary(dictionary);
    }

    private static COSArray colorArray(int size) {
        COSArray array = new COSArray();
        for (int index = 0; index < size; index++) {
            array.add(new COSFloat(0.25f * (index + 1)));
        }
        return array;
    }

    public static void main(String[] args) {
        emit("empty", mk(new COSDictionary()));

        // /R rotation variants.
        for (int[] pair : new int[][] {{0, 0}, {90, 90}, {180, 180}, {270, 270},
                {45, 45}, {360, 360}, {-90, -90}, {12345, 12345}}) {
            COSDictionary d = new COSDictionary();
            d.setItem(COSName.R, COSInteger.get(pair[1]));
            emit("r_" + (pair[0] < 0 ? "neg" + (-pair[0]) : pair[0]), mk(d));
        }
        COSDictionary rFloat = new COSDictionary();
        rFloat.setItem(COSName.R, new COSFloat(90.5f));
        emit("r_float", mk(rFloat));
        COSDictionary rName = new COSDictionary();
        rName.setItem(COSName.R, COSName.getPDFName("Bad"));
        emit("r_name", mk(rName));
        COSDictionary rString = new COSDictionary();
        rString.setItem(COSName.R, new COSString("90"));
        emit("r_string", mk(rString));

        // /BC and /BG color arrays of various arities.
        for (int size : new int[] {0, 1, 2, 3, 4, 5}) {
            COSDictionary d = new COSDictionary();
            d.setItem(COSName.BC, colorArray(size));
            d.setItem(COSName.BG, colorArray(size));
            emit("color_" + size, mk(d));
        }

        // /BC non-numeric component (a name inside a 3-element array).
        COSDictionary bcMixed = new COSDictionary();
        COSArray mixed = new COSArray();
        mixed.add(new COSFloat(0.1f));
        mixed.add(COSName.getPDFName("X"));
        mixed.add(new COSFloat(0.3f));
        bcMixed.setItem(COSName.BC, mixed);
        emit("bc_mixed", mk(bcMixed));

        // /BC not an array.
        COSDictionary bcName = new COSDictionary();
        bcName.setItem(COSName.BC, COSName.getPDFName("Bad"));
        emit("bc_name", mk(bcName));
        COSDictionary bcNull = new COSDictionary();
        bcNull.setItem(COSName.BC, COSNull.NULL);
        emit("bc_null", mk(bcNull));
        COSDictionary bcDict = new COSDictionary();
        bcDict.setItem(COSName.BC, new COSDictionary());
        emit("bc_dict", mk(bcDict));

        // /BC indirect array (size 3).
        COSDictionary bcIndirect = new COSDictionary();
        bcIndirect.setItem(COSName.BC, indirect(colorArray(3)));
        emit("bc_indirect", mk(bcIndirect));

        // Captions: present, wrong type, indirect.
        COSDictionary capOk = new COSDictionary();
        capOk.setItem(COSName.CA, new COSString("Submit"));
        capOk.setItem(COSName.RC, new COSString("Roll Over"));
        capOk.setItem(COSName.AC, new COSString("Alt"));
        emit("cap_ok", mk(capOk));

        COSDictionary capName = new COSDictionary();
        capName.setItem(COSName.CA, COSName.getPDFName("NotString"));
        emit("cap_name", mk(capName));
        COSDictionary capInt = new COSDictionary();
        capInt.setItem(COSName.CA, COSInteger.get(5));
        emit("cap_int", mk(capInt));

        // Icons: stream, non-stream, indirect, null.
        COSDictionary iconStream = new COSDictionary();
        iconStream.setItem(COSName.I, new COSStream());
        iconStream.setItem(COSName.RI, new COSStream());
        iconStream.setItem(COSName.IX, new COSStream());
        emit("icon_stream", mk(iconStream));

        COSDictionary iconDict = new COSDictionary();
        iconDict.setItem(COSName.I, new COSDictionary());
        emit("icon_dict", mk(iconDict));
        COSDictionary iconName = new COSDictionary();
        iconName.setItem(COSName.I, COSName.getPDFName("Bad"));
        emit("icon_name", mk(iconName));
        COSDictionary iconNull = new COSDictionary();
        iconNull.setItem(COSName.I, COSNull.NULL);
        emit("icon_null", mk(iconNull));
        COSDictionary iconIndirect = new COSDictionary();
        iconIndirect.setItem(COSName.I, indirect(new COSStream()));
        emit("icon_indirect", mk(iconIndirect));
    }
}
