import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;

/**
 * Live oracle probe for {@code PDXObject.createXObject(COSBase, PDResources)}
 * /Subtype dispatch (wave 1532). Projects the concrete class produced for each
 * malformed/edge case, or {@code null}, or the thrown exception's message — so a
 * pypdfbox parity test can diff the dispatch decision (Form vs Image vs PS vs
 * TransparencyGroup vs error/null) rather than rendered pixels.
 *
 * Output (UTF-8, one line per case):
 *   CASE &lt;id&gt; result=&lt;ClassSimpleName|null|err:&lt;message&gt;&gt;
 */
public final class XObjectDispatchFuzzProbe {
    private static final String[] CASE_IDS = {
        "img", "form", "ps",
        "unknown", "absent", "empty",
        "sub-str", "sub-int", "sub-null", "sub-arr", "sub-ind-name",
        "base-null", "base-dict", "base-name", "base-int", "base-array",
        "base-ind-stream",
        "form-grp-tr", "form-grp-other", "form-grp-no-s", "form-grp-nondict",
        "form-grp-null", "form-grp-ind", "form-grp-s-str",
        "img-no-res", "form-no-res",
        "ps-extra", "img-empty-stream"
    };

    private static final COSName S = COSName.getPDFName("S");

    private XObjectDispatchFuzzProbe() {}

    private static COSStream stream(String subtype) {
        COSStream stream = new COSStream();
        if (subtype != null) {
            stream.setItem(COSName.SUBTYPE, COSName.getPDFName(subtype));
        }
        return stream;
    }

    private static COSDictionary group(String sValue, boolean asName) {
        COSDictionary g = new COSDictionary();
        if (sValue != null) {
            if (asName) {
                g.setItem(S, COSName.getPDFName(sValue));
            } else {
                g.setItem(S, new COSString(sValue));
            }
        }
        return g;
    }

    private static COSBase base(String caseId) {
        switch (caseId) {
            case "img":
                return stream("Image");
            case "form":
                return stream("Form");
            case "ps":
                return stream("PS");
            case "unknown":
                return stream("Bogus");
            case "absent":
                return stream(null);
            case "empty":
                return new COSStream();
            case "sub-str": {
                COSStream s = new COSStream();
                s.setItem(COSName.SUBTYPE, new COSString("Image"));
                return s;
            }
            case "sub-int": {
                COSStream s = new COSStream();
                s.setItem(COSName.SUBTYPE, COSInteger.get(7));
                return s;
            }
            case "sub-null": {
                COSStream s = new COSStream();
                s.setItem(COSName.SUBTYPE, COSNull.NULL);
                return s;
            }
            case "sub-arr": {
                COSStream s = new COSStream();
                COSArray arr = new COSArray();
                arr.add(COSName.getPDFName("Form"));
                s.setItem(COSName.SUBTYPE, arr);
                return s;
            }
            case "sub-ind-name": {
                COSStream s = new COSStream();
                s.setItem(COSName.SUBTYPE, new COSObject(COSName.getPDFName("Form")));
                return s;
            }
            case "base-null":
                return null;
            case "base-dict":
                return new COSDictionary();
            case "base-name":
                return COSName.getPDFName("Form");
            case "base-int":
                return COSInteger.get(3);
            case "base-array":
                return new COSArray();
            case "base-ind-stream":
                return new COSObject(stream("Form"));
            case "form-grp-tr": {
                COSStream s = stream("Form");
                s.setItem(COSName.GROUP, group("Transparency", true));
                return s;
            }
            case "form-grp-other": {
                COSStream s = stream("Form");
                s.setItem(COSName.GROUP, group("Other", true));
                return s;
            }
            case "form-grp-no-s": {
                COSStream s = stream("Form");
                s.setItem(COSName.GROUP, group(null, true));
                return s;
            }
            case "form-grp-nondict": {
                COSStream s = stream("Form");
                s.setItem(COSName.GROUP, COSInteger.get(1));
                return s;
            }
            case "form-grp-null": {
                COSStream s = stream("Form");
                s.setItem(COSName.GROUP, COSNull.NULL);
                return s;
            }
            case "form-grp-ind": {
                COSStream s = stream("Form");
                s.setItem(COSName.GROUP, new COSObject(group("Transparency", true)));
                return s;
            }
            case "form-grp-s-str": {
                COSStream s = stream("Form");
                s.setItem(COSName.GROUP, group("Transparency", false));
                return s;
            }
            case "img-no-res":
                return stream("Image");
            case "form-no-res":
                return stream("Form");
            case "ps-extra": {
                COSStream s = stream("PS");
                s.setItem(COSName.getPDFName("Foo"), COSInteger.get(9));
                return s;
            }
            case "img-empty-stream":
                return stream("Image");
            default:
                throw new IllegalArgumentException(caseId);
        }
    }

    private static boolean noResources(String caseId) {
        return caseId.equals("img-no-res")
                || caseId.equals("form-no-res")
                || caseId.equals("base-null");
    }

    private static String result(String caseId) {
        COSBase b = base(caseId);
        PDResources res = noResources(caseId) ? null : new PDResources();
        try {
            PDXObject xobject = PDXObject.createXObject(b, res);
            return xobject == null ? "null" : xobject.getClass().getSimpleName();
        } catch (Exception exception) {
            return "err:" + exception.getMessage();
        }
    }

    public static void main(String[] args) {
        java.io.PrintStream out;
        try {
            out = new java.io.PrintStream(System.out, true, "UTF-8");
        } catch (java.io.UnsupportedEncodingException e) {
            throw new RuntimeException(e);
        }
        for (String caseId : CASE_IDS) {
            out.println("CASE " + caseId + " result=" + result(caseId));
        }
    }
}
