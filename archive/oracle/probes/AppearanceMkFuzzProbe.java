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
 * Direct malformed-input oracle for the WIDGET /MK appearance-characteristics
 * surface, PDFBox 3.0.7 — wave 1539.
 *
 * Complements AppearanceCharacteristicsFuzzProbe (wave 1529) by hammering the
 * READ surface of every PUBLIC accessor that PDFBox 3.0.7 actually exposes on
 * PDAppearanceCharacteristicsDictionary — verified via `javap`:
 *
 *   getRotation, getBorderColour, getBackground, getNormalCaption,
 *   getRolloverCaption, getAlternateCaption, getNormalIcon, getRolloverIcon,
 *   getAlternateIcon.
 *
 * NOTE: PDFBox 3.0.7 has NO getTextPosition / getIconFit / PDIconFit inner
 * class and NO COSName.TP constant. pypdfbox adds get_text_position /
 * get_icon_fit / PDIconFit as a forward-looking extension; those have no live
 * 3.0.7 oracle counterpart and are pinned Python-side in the parity test with
 * a divergence note (not projected here).
 *
 * This probe widens the /R rotation read fuzzing (negative-non-90, huge, float
 * truncation) and exercises the typed-form icon getters over malformed entries
 * — the cases AppearanceCharacteristicsFuzzProbe did not enumerate.
 */
public final class AppearanceMkFuzzProbe {

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

    private static String text(String value) {
        return value == null ? "none" : value.replace(' ', '_');
    }

    private static String icon(PDFormXObject form) {
        return form == null ? "none" : "form";
    }

    private static PDAppearanceCharacteristicsDictionary mk(COSDictionary dictionary) {
        return new PDAppearanceCharacteristicsDictionary(dictionary);
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

    private static COSArray colorArray(float... values) {
        COSArray array = new COSArray();
        for (float value : values) {
            array.add(new COSFloat(value));
        }
        return array;
    }

    public static void main(String[] args) {
        emit("empty", mk(new COSDictionary()));

        // ---- /R rotation as a raw int (getRotation = getInt(/R, 0)). ----
        // Widen wave 1529: negative-non-90, multi-turn, exactly 360/720.
        for (int value : new int[] {0, 90, 180, 270, 45, 360, 720, -90, -180, -270, -45, 12345, 99999}) {
            COSDictionary d = new COSDictionary();
            d.setItem(COSName.R, COSInteger.get(value));
            emit("r_" + (value < 0 ? "neg" + (-value) : value), mk(d));
        }
        // /R as a COSFloat — getInt truncates toward zero in PDFBox.
        COSDictionary rFloatPos = new COSDictionary();
        rFloatPos.setItem(COSName.R, new COSFloat(90.9f));
        emit("r_float_pos", mk(rFloatPos));
        COSDictionary rFloatNeg = new COSDictionary();
        rFloatNeg.setItem(COSName.R, new COSFloat(-90.9f));
        emit("r_float_neg", mk(rFloatNeg));
        COSDictionary rName = new COSDictionary();
        rName.setItem(COSName.R, COSName.getPDFName("Bad"));
        emit("r_name", mk(rName));
        COSDictionary rString = new COSDictionary();
        rString.setItem(COSName.R, new COSString("90"));
        emit("r_string", mk(rString));
        COSDictionary rNull = new COSDictionary();
        rNull.setItem(COSName.R, COSNull.NULL);
        emit("r_null", mk(rNull));

        // ---- /BC and /BG arity dispatch (every length 0..5). ----
        for (int size : new int[] {0, 1, 2, 3, 4, 5}) {
            COSDictionary d = new COSDictionary();
            float[] comps = new float[size];
            for (int i = 0; i < size; i++) {
                comps[i] = 0.2f * (i + 1);
            }
            d.setItem(COSName.BC, colorArray(comps));
            d.setItem(COSName.BG, colorArray(comps));
            emit("color_" + size, mk(d));
        }

        // /BC transparent (empty) vs /BG valid gray — asymmetric arities.
        COSDictionary asym = new COSDictionary();
        asym.setItem(COSName.BC, colorArray());
        asym.setItem(COSName.BG, colorArray(0.5f));
        emit("asym", mk(asym));

        // /BC non-numeric component inside a length-3 array.
        COSDictionary bcMixed = new COSDictionary();
        COSArray mixed = new COSArray();
        mixed.add(new COSFloat(0.1f));
        mixed.add(COSName.getPDFName("X"));
        mixed.add(new COSFloat(0.3f));
        bcMixed.setItem(COSName.BC, mixed);
        emit("bc_mixed", mk(bcMixed));

        // /BC with an integer component (not a float).
        COSDictionary bcInt = new COSDictionary();
        COSArray ints = new COSArray();
        ints.add(COSInteger.get(0));
        ints.add(COSInteger.get(1));
        ints.add(COSInteger.get(0));
        bcInt.setItem(COSName.BC, ints);
        emit("bc_int", mk(bcInt));

        // /BC wrong types.
        COSDictionary bcName = new COSDictionary();
        bcName.setItem(COSName.BC, COSName.getPDFName("Bad"));
        emit("bc_name", mk(bcName));
        COSDictionary bcDict = new COSDictionary();
        bcDict.setItem(COSName.BC, new COSDictionary());
        emit("bc_dict", mk(bcDict));
        COSDictionary bcIndirect = new COSDictionary();
        bcIndirect.setItem(COSName.BC, indirect(colorArray(0.1f, 0.2f, 0.3f)));
        emit("bc_indirect", mk(bcIndirect));

        // ---- captions: present / wrong type / empty / indirect. ----
        COSDictionary capOk = new COSDictionary();
        capOk.setItem(COSName.CA, new COSString("Submit Now"));
        capOk.setItem(COSName.getPDFName("RC"), new COSString("Roll"));
        capOk.setItem(COSName.getPDFName("AC"), new COSString("Alt"));
        emit("cap_ok", mk(capOk));
        COSDictionary capEmpty = new COSDictionary();
        capEmpty.setItem(COSName.CA, new COSString(""));
        emit("cap_empty", mk(capEmpty));
        COSDictionary capName = new COSDictionary();
        capName.setItem(COSName.CA, COSName.getPDFName("NotString"));
        emit("cap_name", mk(capName));
        COSDictionary capInt = new COSDictionary();
        capInt.setItem(COSName.CA, COSInteger.get(5));
        emit("cap_int", mk(capInt));
        COSDictionary capIndirect = new COSDictionary();
        capIndirect.setItem(COSName.CA, indirect(new COSString("Ind")));
        emit("cap_indirect", mk(capIndirect));

        // ---- icons: stream / non-stream / null / indirect-stream. ----
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
