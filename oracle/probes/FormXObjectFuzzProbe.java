import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;
import org.apache.pdfbox.pdmodel.graphics.form.PDTransparencyGroup;
import org.apache.pdfbox.pdmodel.graphics.form.PDTransparencyGroupAttributes;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;

/**
 * Malformed transparency-group attribute oracle for wave 1550.
 *
 * Complements {@code FormXObjectDictionaryFuzzProbe} (wave 1521), which
 * exercises the FORM-LEVEL accessors and treats {@code /Group} only at the
 * presence level. This probe drills into the transparency-group ATTRIBUTES
 * dictionary internals (PDF 32000-1 Table 96): the {@code /S} group subtype,
 * {@code /CS} group colour space, the {@code /I} isolated flag, the {@code /K}
 * knockout flag — each with valid / wrong-type / missing / indirect /
 * inverted shapes. It also projects the XObject-factory dispatch
 * ({@code createXObject}): whether a given {@code /Group} produces a
 * {@code PDTransparencyGroup} or a plain {@code PDFormXObject}.
 *
 * Output (UTF-8, stdout): one line per case, parseable, of the form
 *   CASE &lt;id&gt; type=&lt;PlainForm|TransparencyGroup&gt; group=&lt;present|none&gt;
 *        subtype=&lt;name|none&gt; iso=&lt;true|false&gt; knock=&lt;true|false&gt;
 *        cs=&lt;name|present|none|err&gt; istg=&lt;true|false&gt;
 */
public final class FormXObjectFuzzProbe {
    private static final String[] CASE_IDS = {
        // --- /Group container shape (drives factory dispatch + getGroup) ---
        "g-none", "g-empty", "g-nondict", "g-null", "g-indirect-dict",
        // --- /S subtype ---
        "s-transparency", "s-other", "s-nonname-int", "s-nonname-bool",
        "s-null", "s-missing", "s-indirect",
        // --- /I isolated flag ---
        "i-true", "i-false", "i-int", "i-name", "i-null", "i-missing",
        "i-indirect-true",
        // --- /K knockout flag ---
        "k-true", "k-false", "k-int", "k-string", "k-null", "k-missing",
        "k-indirect-true",
        // --- /CS group colour space ---
        "cs-devgray", "cs-devrgb", "cs-devcmyk", "cs-bad-name", "cs-int",
        "cs-empty-array", "cs-null", "cs-missing", "cs-indirect-name",
        // --- combos ---
        "full-iso-knock", "tr-no-i-no-k", "non-tr-with-cs",
    };

    private static final COSName CS = COSName.getPDFName("CS");
    private static final COSName ISO = COSName.getPDFName("I");
    private static final COSName KNOCK = COSName.getPDFName("K");
    private static final COSName GROUP = COSName.getPDFName("Group");
    private static final COSName S = COSName.getPDFName("S");

    private FormXObjectFuzzProbe() {}

    private static COSObject indirect(COSBase value) {
        return new COSObject(value);
    }

    /** A bare transparency group dictionary: /Type /Group, /S /Transparency. */
    private static COSDictionary group() {
        COSDictionary dictionary = new COSDictionary();
        dictionary.setItem(COSName.TYPE, COSName.getPDFName("Group"));
        dictionary.setItem(S, COSName.getPDFName("Transparency"));
        return dictionary;
    }

    private static COSStream formStream(COSBase groupValue) {
        COSStream stream = new COSStream();
        stream.setItem(COSName.SUBTYPE, COSName.FORM);
        stream.setItem(COSName.BBOX, numbers(0, 0, 100, 100));
        if (groupValue != null) {
            stream.setItem(GROUP, groupValue);
        }
        return stream;
    }

    private static COSArray numbers(float... values) {
        COSArray array = new COSArray();
        for (float value : values) {
            array.add(new COSFloat(value));
        }
        return array;
    }

    private static COSStream build(String caseId) {
        COSDictionary grp;
        switch (caseId) {
            case "g-none":
                return formStream(null);
            case "g-empty":
                return formStream(new COSDictionary());
            case "g-nondict":
                return formStream(COSInteger.get(5));
            case "g-null":
                return formStream(COSNull.NULL);
            case "g-indirect-dict":
                return formStream(indirect(group()));

            case "s-transparency":
                return formStream(group());
            case "s-other":
                grp = group();
                grp.setItem(S, COSName.getPDFName("Mask"));
                return formStream(grp);
            case "s-nonname-int":
                grp = group();
                grp.setItem(S, COSInteger.get(7));
                return formStream(grp);
            case "s-nonname-bool":
                grp = group();
                grp.setItem(S, COSBoolean.TRUE);
                return formStream(grp);
            case "s-null":
                grp = group();
                grp.setItem(S, COSNull.NULL);
                return formStream(grp);
            case "s-missing":
                grp = new COSDictionary();
                grp.setItem(COSName.TYPE, COSName.getPDFName("Group"));
                return formStream(grp);
            case "s-indirect":
                grp = new COSDictionary();
                grp.setItem(S, indirect(COSName.getPDFName("Transparency")));
                return formStream(grp);

            case "i-true":
                grp = group();
                grp.setItem(ISO, COSBoolean.TRUE);
                return formStream(grp);
            case "i-false":
                grp = group();
                grp.setItem(ISO, COSBoolean.FALSE);
                return formStream(grp);
            case "i-int":
                grp = group();
                grp.setItem(ISO, COSInteger.get(1));
                return formStream(grp);
            case "i-name":
                grp = group();
                grp.setItem(ISO, COSName.getPDFName("true"));
                return formStream(grp);
            case "i-null":
                grp = group();
                grp.setItem(ISO, COSNull.NULL);
                return formStream(grp);
            case "i-missing":
                return formStream(group());
            case "i-indirect-true":
                grp = group();
                grp.setItem(ISO, indirect(COSBoolean.TRUE));
                return formStream(grp);

            case "k-true":
                grp = group();
                grp.setItem(KNOCK, COSBoolean.TRUE);
                return formStream(grp);
            case "k-false":
                grp = group();
                grp.setItem(KNOCK, COSBoolean.FALSE);
                return formStream(grp);
            case "k-int":
                grp = group();
                grp.setItem(KNOCK, COSInteger.get(0));
                return formStream(grp);
            case "k-string":
                grp = group();
                grp.setString(KNOCK, "true");
                return formStream(grp);
            case "k-null":
                grp = group();
                grp.setItem(KNOCK, COSNull.NULL);
                return formStream(grp);
            case "k-missing":
                return formStream(group());
            case "k-indirect-true":
                grp = group();
                grp.setItem(KNOCK, indirect(COSBoolean.TRUE));
                return formStream(grp);

            case "cs-devgray":
                grp = group();
                grp.setItem(CS, COSName.getPDFName("DeviceGray"));
                return formStream(grp);
            case "cs-devrgb":
                grp = group();
                grp.setItem(CS, COSName.getPDFName("DeviceRGB"));
                return formStream(grp);
            case "cs-devcmyk":
                grp = group();
                grp.setItem(CS, COSName.getPDFName("DeviceCMYK"));
                return formStream(grp);
            case "cs-bad-name":
                grp = group();
                grp.setItem(CS, COSName.getPDFName("NotAColorSpace"));
                return formStream(grp);
            case "cs-int":
                grp = group();
                grp.setItem(CS, COSInteger.get(3));
                return formStream(grp);
            case "cs-empty-array":
                grp = group();
                grp.setItem(CS, new COSArray());
                return formStream(grp);
            case "cs-null":
                grp = group();
                grp.setItem(CS, COSNull.NULL);
                return formStream(grp);
            case "cs-missing":
                return formStream(group());
            case "cs-indirect-name":
                grp = group();
                grp.setItem(CS, indirect(COSName.getPDFName("DeviceRGB")));
                return formStream(grp);

            case "full-iso-knock":
                grp = group();
                grp.setItem(ISO, COSBoolean.TRUE);
                grp.setItem(KNOCK, COSBoolean.TRUE);
                grp.setItem(CS, COSName.getPDFName("DeviceRGB"));
                return formStream(grp);
            case "tr-no-i-no-k":
                return formStream(group());
            case "non-tr-with-cs":
                grp = new COSDictionary();
                grp.setItem(S, COSName.getPDFName("Mask"));
                grp.setItem(CS, COSName.getPDFName("DeviceGray"));
                return formStream(grp);

            default:
                throw new IllegalArgumentException(caseId);
        }
    }

    private static String csProjection(PDTransparencyGroupAttributes attrs) {
        try {
            PDColorSpace cs = attrs.getColorSpace();
            if (cs == null) {
                return "none";
            }
            String name = cs.getName();
            return name == null ? "present" : name;
        } catch (RuntimeException | java.io.IOException exception) {
            return "err";
        }
    }

    private static String project(String caseId) {
        COSStream stream = build(caseId);
        PDXObject xobject;
        try {
            xobject = PDXObject.createXObject(stream, null);
        } catch (java.io.IOException exception) {
            return "CASE " + caseId + " type=err";
        }
        String type = xobject instanceof PDTransparencyGroup
                ? "TransparencyGroup" : "PlainForm";
        PDFormXObject form = (PDFormXObject) xobject;
        PDTransparencyGroupAttributes attrs = form.getGroup();
        if (attrs == null) {
            return "CASE " + caseId + " type=" + type + " group=none"
                    + " subtype=none iso=false knock=false cs=none istg=false";
        }
        COSName subtype = attrs.getCOSObject().getCOSName(S);
        String subtypeName = subtype == null ? "none" : subtype.getName();
        // PDTransparencyGroupAttributes has no public isTransparencyGroup();
        // mirror the dispatch predicate (subtype == Transparency).
        boolean istg = subtype != null && subtype.getName().equals("Transparency");
        return "CASE " + caseId
                + " type=" + type
                + " group=present"
                + " subtype=" + subtypeName
                + " iso=" + attrs.isIsolated()
                + " knock=" + attrs.isKnockout()
                + " cs=" + csProjection(attrs)
                + " istg=" + istg;
    }

    public static void main(String[] args) {
        for (String caseId : CASE_IDS) {
            System.out.println(project(caseId));
        }
    }
}
