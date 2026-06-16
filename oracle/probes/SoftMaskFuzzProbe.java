import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.graphics.form.PDTransparencyGroup;
import org.apache.pdfbox.pdmodel.graphics.state.PDSoftMask;

/**
 * Complementary malformed-dictionary oracle for PDFBox 3.0.7 PDSoftMask,
 * targeting fuzz angles NOT covered by {@code SoftMaskDictionaryFuzzProbe}:
 *
 * <ul>
 *   <li>{@code /G} stream whose {@code /Subtype} is a COSString (e.g.
 *       {@code (Form)} / {@code (Image)} / {@code (Bad)}) — exercises the
 *       getNameAsString read path inside getGroup → createXObject. A
 *       name-only read would mis-wrap these; getNameAsString decodes the
 *       string so a string {@code (Form)} transparency-group is recognised,
 *       a string {@code (Image)} resolves to null (not a group), and a
 *       string {@code (Bad)} raises.</li>
 *   <li>indirect-reference variants of the string-subtype cases.</li>
 *   <li>{@code /Type} key fuzz (does the wrapper care about /Type /Mask?).</li>
 *   <li>repeated-call identity of getGroup / getBackdropColor (caching).</li>
 * </ul>
 *
 * Output (UTF-8, stdout): one {@code FUZZ <name> <field>=<value> ...} line
 * per case so the companion pytest can key on the leading two tokens.
 */
public final class SoftMaskFuzzProbe {
    private static final COSName TAG = COSName.getPDFName("Tag");

    private static COSObject indirect(COSBase value) {
        return new COSObject(value);
    }

    private static COSStream stringSubtype(String subtype, boolean transparency) {
        COSStream stream = new COSStream();
        if (subtype != null) {
            stream.setItem(COSName.SUBTYPE, new COSString(subtype));
        }
        stream.setItem(COSName.RESOURCES, new COSDictionary());
        stream.setName(TAG, "tagged");
        if (transparency) {
            COSDictionary group = new COSDictionary();
            group.setName(COSName.S, "Transparency");
            stream.setItem(COSName.GROUP, group);
        }
        return stream;
    }

    private static String group(PDSoftMask mask) {
        try {
            PDTransparencyGroup value = mask.getGroup();
            return value == null ? "null" : "group";
        } catch (Exception exception) {
            return "ERR";
        }
    }

    private static void emitGroup(String name, COSBase groupValue) {
        COSDictionary dictionary = new COSDictionary();
        if (groupValue != null) {
            dictionary.setItem(COSName.G, groupValue);
        }
        PDSoftMask mask = new PDSoftMask(dictionary);
        System.out.println("FUZZ " + name + " g=" + group(mask));
    }

    private static void emitGroupIdentity(String name, COSBase groupValue) {
        COSDictionary dictionary = new COSDictionary();
        dictionary.setItem(COSName.G, groupValue);
        PDSoftMask mask = new PDSoftMask(dictionary);
        try {
            PDTransparencyGroup first = mask.getGroup();
            PDTransparencyGroup second = mask.getGroup();
            String same;
            if (first == null) {
                same = second == null ? "both_null" : "drift";
            } else {
                same = first == second ? "same" : "other";
            }
            System.out.println("FUZZ " + name + " g=" + group(mask) + " identity=" + same);
        } catch (Exception exception) {
            System.out.println("FUZZ " + name + " g=ERR identity=ERR");
        }
    }

    private static void emitBackdropIdentity(String name) {
        COSDictionary dictionary = new COSDictionary();
        COSArray bc = new COSArray();
        bc.add(COSInteger.ZERO);
        bc.add(COSInteger.ONE);
        dictionary.setItem(COSName.BC, bc);
        PDSoftMask mask = new PDSoftMask(dictionary);
        COSArray first = mask.getBackdropColor();
        COSArray second = mask.getBackdropColor();
        System.out.println(
                "FUZZ " + name
                        + " bc=" + (first == null ? "null" : "array:" + first.size())
                        + " identity=" + (first == second ? "same" : "other"));
    }

    private static void emitTypeKey(String name, COSBase typeValue) {
        COSDictionary dictionary = new COSDictionary();
        dictionary.setName(COSName.S, "Luminosity");
        if (typeValue != null) {
            dictionary.setItem(COSName.TYPE, typeValue);
        }
        PDSoftMask mask = new PDSoftMask(dictionary);
        COSName subtype = mask.getSubType();
        System.out.println(
                "FUZZ " + name + " s=" + (subtype == null ? "null" : subtype.getName()));
    }

    public static void main(String[] args) {
        // /Subtype carried as a COSString — the getNameAsString surface.
        emitGroup("str_form_plain", stringSubtype("Form", false));
        emitGroup("str_form_transp", stringSubtype("Form", true));
        emitGroup("str_image", stringSubtype("Image", false));
        emitGroup("str_ps", stringSubtype("PS", false));
        emitGroup("str_bad", stringSubtype("Bad", false));
        emitGroup("str_empty", stringSubtype("", false));

        // Indirect references wrapping the string-subtype streams.
        emitGroup("str_indirect_transp", indirect(stringSubtype("Form", true)));
        emitGroup("str_indirect_image", indirect(stringSubtype("Image", false)));
        emitGroup("str_indirect_bad", indirect(stringSubtype("Bad", false)));

        // Repeated-call identity (caching) of getGroup / getBackdropColor.
        emitGroupIdentity("identity_transp", stringSubtype("Form", true));
        emitGroupIdentity("identity_image", stringSubtype("Image", false));
        emitBackdropIdentity("identity_backdrop");

        // /Type key fuzz — does the wrapper validate /Type /Mask?
        emitTypeKey("type_absent", null);
        emitTypeKey("type_mask", COSName.MASK);
        emitTypeKey("type_wrong", COSName.getPDFName("NotMask"));
        emitTypeKey("type_integer", COSInteger.ONE);
        emitTypeKey("type_null", COSNull.NULL);
    }
}
