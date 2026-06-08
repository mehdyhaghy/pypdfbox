import java.lang.reflect.Method;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.interactive.viewerpreferences.PDViewerPreferences;

/** Differential malformed-dictionary probe for PDViewerPreferences (wave 1521). */
public final class ViewerPreferencesFuzzProbe {
    private static final String[] BOOLEAN_KEYS = {
        "HideToolbar", "HideMenubar", "HideWindowUI", "FitWindow",
        "CenterWindow", "DisplayDocTitle"
    };

    private static final String[] NAME_KEYS = {
        "NonFullScreenPageMode", "Direction", "ViewArea", "ViewClip",
        "PrintArea", "PrintClip", "Duplex", "PrintScaling"
    };

    private static COSName name(String value) {
        return COSName.getPDFName(value);
    }

    private static COSArray array(COSBase... values) {
        COSArray result = new COSArray();
        for (COSBase value : values) {
            result.add(value);
        }
        return result;
    }

    private static String cell(String value) {
        return value == null ? "null" : value;
    }

    private static String raw(COSDictionary dictionary, String key) {
        COSBase value = dictionary.getDictionaryObject(name(key));
        if (value == null) {
            return "null";
        }
        if (value instanceof COSBoolean) {
            return "bool:" + ((COSBoolean) value).getValue();
        }
        if (value instanceof COSName) {
            return "name:" + ((COSName) value).getName();
        }
        if (value instanceof COSString) {
            return "string:" + ((COSString) value).getString();
        }
        if (value instanceof COSInteger) {
            return "int:" + ((COSInteger) value).longValue();
        }
        if (value instanceof COSFloat) {
            return "float:" + ((COSFloat) value).floatValue();
        }
        if (value instanceof COSArray) {
            return "array:" + ((COSArray) value).size();
        }
        if (value instanceof COSDictionary) {
            return "dict";
        }
        return value.getClass().getSimpleName();
    }

    private static COSBase booleanValue(String caseName) {
        switch (caseName) {
            case "true":
                return COSBoolean.TRUE;
            case "false":
                return COSBoolean.FALSE;
            case "null":
                return COSNull.NULL;
            case "int":
                return COSInteger.ONE;
            case "name":
                return name("true");
            case "string":
                return new COSString("true");
            case "ind_true":
                return new COSObject(COSBoolean.TRUE);
            case "ind_null":
                return new COSObject(COSNull.NULL);
            default:
                throw new IllegalArgumentException(caseName);
        }
    }

    private static void runBooleans(String caseName) {
        COSDictionary dictionary = new COSDictionary();
        if (!"absent".equals(caseName)) {
            COSBase value = booleanValue(caseName);
            for (String key : BOOLEAN_KEYS) {
                dictionary.setItem(name(key), value);
            }
        }
        PDViewerPreferences prefs = new PDViewerPreferences(dictionary);
        System.out.println("ht=" + prefs.hideToolbar()
                + " hm=" + prefs.hideMenubar()
                + " hw=" + prefs.hideWindowUI()
                + " fw=" + prefs.fitWindow()
                + " cw=" + prefs.centerWindow()
                + " dd=" + prefs.displayDocTitle());
    }

    private static COSBase nameValue(String caseName, String validValue) {
        switch (caseName) {
            case "valid":
                return name(validValue);
            case "bogus":
                return name("Bogus");
            case "string":
                return new COSString("Text");
            case "empty":
                return new COSString("");
            case "wrong":
                return COSInteger.ONE;
            case "null":
                return COSNull.NULL;
            case "ind_valid":
                return new COSObject(name(validValue));
            case "ind_string":
                return new COSObject(new COSString("Text"));
            case "ind_null":
                return new COSObject(COSNull.NULL);
            default:
                throw new IllegalArgumentException(caseName);
        }
    }

    private static void runNames(String caseName) {
        String[] validValues = {
            "UseOutlines", "R2L", "MediaBox", "BleedBox",
            "TrimBox", "ArtBox", "Simplex", "None"
        };
        COSDictionary dictionary = new COSDictionary();
        if (!"absent".equals(caseName)) {
            for (int i = 0; i < NAME_KEYS.length; i++) {
                dictionary.setItem(name(NAME_KEYS[i]), nameValue(caseName, validValues[i]));
            }
        }
        PDViewerPreferences prefs = new PDViewerPreferences(dictionary);
        System.out.println("nfs=" + cell(prefs.getNonFullScreenPageMode())
                + " dir=" + cell(prefs.getReadingDirection())
                + " va=" + cell(prefs.getViewArea())
                + " vc=" + cell(prefs.getViewClip())
                + " pa=" + cell(prefs.getPrintArea())
                + " pc=" + cell(prefs.getPrintClip())
                + " dup=" + cell(prefs.getDuplex())
                + " ps=" + cell(prefs.getPrintScaling()));
    }

    private static void runSetter(String setter) {
        PDViewerPreferences prefs = new PDViewerPreferences();
        String key;
        switch (setter) {
            case "ht":
                prefs.setHideToolbar(true);
                key = "HideToolbar";
                break;
            case "hm":
                prefs.setHideMenubar(true);
                key = "HideMenubar";
                break;
            case "hw":
                prefs.setHideWindowUI(true);
                key = "HideWindowUI";
                break;
            case "fw":
                prefs.setFitWindow(true);
                key = "FitWindow";
                break;
            case "cw":
                prefs.setCenterWindow(true);
                key = "CenterWindow";
                break;
            case "dd":
                prefs.setDisplayDocTitle(true);
                key = "DisplayDocTitle";
                break;
            case "nfs":
                prefs.setNonFullScreenPageMode(
                        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseOutlines);
                key = "NonFullScreenPageMode";
                break;
            case "dir":
                prefs.setReadingDirection(PDViewerPreferences.READING_DIRECTION.R2L);
                key = "Direction";
                break;
            case "va":
                prefs.setViewArea(PDViewerPreferences.BOUNDARY.MediaBox);
                key = "ViewArea";
                break;
            case "vc":
                prefs.setViewClip(PDViewerPreferences.BOUNDARY.BleedBox);
                key = "ViewClip";
                break;
            case "pa":
                prefs.setPrintArea(PDViewerPreferences.BOUNDARY.TrimBox);
                key = "PrintArea";
                break;
            case "pc":
                prefs.setPrintClip(PDViewerPreferences.BOUNDARY.ArtBox);
                key = "PrintClip";
                break;
            case "dup":
                prefs.setDuplex(PDViewerPreferences.DUPLEX.Simplex);
                key = "Duplex";
                break;
            case "ps":
                prefs.setPrintScaling(PDViewerPreferences.PRINT_SCALING.None);
                key = "PrintScaling";
                break;
            default:
                throw new IllegalArgumentException(setter);
        }
        System.out.println(raw(prefs.getCOSObject(), key));
    }

    private static boolean hasMethod(String methodName) {
        for (Method method : PDViewerPreferences.class.getMethods()) {
            if (method.getName().equals(methodName)) {
                return true;
            }
        }
        return false;
    }

    private static COSBase enrichmentValue(String surface, String caseName) {
        if ("pick".equals(surface)) {
            switch (caseName) {
                case "true":
                    return COSBoolean.TRUE;
                case "wrong":
                    return COSInteger.ONE;
                case "null":
                    return COSNull.NULL;
                case "ind_false":
                    return new COSObject(COSBoolean.FALSE);
                default:
                    throw new IllegalArgumentException(caseName);
            }
        }
        if ("num".equals(surface)) {
            switch (caseName) {
                case "pos":
                    return COSInteger.get(3);
                case "wrong":
                    return name("Three");
                case "null":
                    return COSNull.NULL;
                case "ind_zero":
                    return new COSObject(COSInteger.ZERO);
                default:
                    throw new IllegalArgumentException(caseName);
            }
        }
        if ("range".equals(surface)) {
            switch (caseName) {
                case "array":
                    return array(COSInteger.ONE, COSInteger.get(3));
                case "wrong":
                    return new COSDictionary();
                case "null":
                    return COSNull.NULL;
                case "ind_array":
                    return new COSObject(array(COSInteger.TWO, COSInteger.get(4)));
                default:
                    throw new IllegalArgumentException(caseName);
            }
        }
        if ("enforce".equals(surface)) {
            switch (caseName) {
                case "array":
                    return array(name("PrintScaling"), name("Duplex"));
                case "wrong":
                    return name("PrintScaling");
                case "null":
                    return COSNull.NULL;
                case "ind_array":
                    return new COSObject(array(name("Direction"), COSInteger.ONE));
                default:
                    throw new IllegalArgumentException(caseName);
            }
        }
        throw new IllegalArgumentException(surface);
    }

    private static void runEnrichment(String surface, String caseName) {
        String key;
        String method;
        switch (surface) {
            case "pick":
                key = "PickTrayByPDFSize";
                method = "getPickTrayByPDFSize";
                break;
            case "num":
                key = "NumCopies";
                method = "getNumCopies";
                break;
            case "range":
                key = "PrintPageRange";
                method = "getPrintPageRange";
                break;
            case "enforce":
                key = "Enforce";
                method = "getEnforce";
                break;
            default:
                throw new IllegalArgumentException(surface);
        }
        COSDictionary dictionary = new COSDictionary();
        if (!"absent".equals(caseName)) {
            dictionary.setItem(name(key), enrichmentValue(surface, caseName));
        }
        String support = hasMethod(method) ? "present" : "unsupported";
        System.out.println("api=" + support + " raw=" + raw(dictionary, key));
    }

    public static void main(String[] args) {
        switch (args[0]) {
            case "bool":
                runBooleans(args[1]);
                break;
            case "name":
                runNames(args[1]);
                break;
            case "setter":
                runSetter(args[1]);
                break;
            case "enrichment":
                runEnrichment(args[1], args[2]);
                break;
            default:
                throw new IllegalArgumentException(args[0]);
        }
    }
}
