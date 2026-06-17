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
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDPropBuild;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDPropBuildDataDict;

/**
 * Differential malformed-dictionary probe for the signature {@code /Prop_Build}
 * build-properties dictionaries — {@link PDPropBuild} and
 * {@link PDPropBuildDataDict} — Apache PDFBox 3.0.7 (wave 1538, agent E).
 *
 * <p>Two surfaces:
 * <ul>
 *   <li>{@code build &lt;case&gt;}: project which of {@code getFilter()},
 *       {@code getPubSec()}, {@code getApp()} return a wrapper vs {@code null}
 *       when the {@code /Filter} {@code /PubSec} {@code /App} entries are absent,
 *       present-as-dict, a wrong type, {@code COSNull}, or an indirect ref to a
 *       dictionary. Each accessor goes through {@code getCOSDictionary}.</li>
 *   <li>{@code data &lt;field&gt; &lt;case&gt;}: project a single
 *       {@link PDPropBuildDataDict} accessor over a malformed entry —
 *       {@code getName} ({@code getNameAsString}: name OR string),
 *       {@code getDate} ({@code getString}), {@code getVersion} ({@code /REx}
 *       getString), {@code getRevision} ({@code /R} getLong, default -1),
 *       {@code getMinimumRevision} ({@code /V} getLong), {@code getPreRelease}
 *       ({@code /PreRelease} getBoolean default false), {@code getOS}
 *       (getCOSArray.getName(0) else getString), {@code getNonEFontNoWarn}
 *       (getBoolean default true), {@code getTrustedMode} (getBoolean default
 *       false).</li>
 * </ul>
 *
 * <p>Output: one {@code key=value} line per accessor (build surface) or a single
 * {@code value=...} line (data surface). {@code null} stands in for a Java
 * {@code null} return.
 */
public final class PropBuildFuzzProbe {

    static COSName name(String value) {
        return COSName.getPDFName(value);
    }

    static COSArray array(COSBase... values) {
        COSArray result = new COSArray();
        for (COSBase value : values) {
            result.add(value);
        }
        return result;
    }

    static String nz(String s) {
        return s == null ? "null" : s;
    }

    static String present(PDPropBuildDataDict d) {
        return d == null ? "null" : "dict";
    }

    // ---- build surface: /Filter //PubSec //App sub-dict presence ----

    static COSBase subDictValue(String caseName) {
        switch (caseName) {
            case "absent":
                return null;
            case "dict":
                return new COSDictionary();
            case "wrong_int":
                return COSInteger.ONE;
            case "wrong_name":
                return name("Filter");
            case "wrong_array":
                return array(COSInteger.ONE);
            case "null":
                return COSNull.NULL;
            case "ind_dict":
                return new COSObject(new COSDictionary());
            case "ind_null":
                return new COSObject(COSNull.NULL);
            default:
                throw new IllegalArgumentException(caseName);
        }
    }

    static void runBuild(String caseName) {
        COSDictionary dict = new COSDictionary();
        COSBase value = subDictValue(caseName);
        // "absent" returns Java null -> keys stay off; every other case sets a
        // (possibly COSNull) value under all three keys.
        if (value != null) {
            dict.setItem(COSName.FILTER, value);
            dict.setItem(COSName.PUB_SEC, value);
            dict.setItem(COSName.APP, value);
        }
        PDPropBuild build = new PDPropBuild(dict);
        System.out.println("filter=" + present(build.getFilter())
                + " pubsec=" + present(build.getPubSec())
                + " app=" + present(build.getApp()));
    }

    // ---- data surface: PDPropBuildDataDict accessors ----

    static COSBase fieldValue(String caseName) {
        switch (caseName) {
            case "absent":
                return null;
            case "name":
                return name("Acrobat");
            case "string":
                return new COSString("Acrobat");
            case "empty_string":
                return new COSString("");
            case "int":
                return COSInteger.get(7);
            case "neg_int":
                return COSInteger.get(-5);
            case "float":
                return new COSFloat(2.5f);
            case "bool_true":
                return COSBoolean.TRUE;
            case "bool_false":
                return COSBoolean.FALSE;
            case "name_arr":
                return array(name("Win"), name("Mac"));
            case "empty_arr":
                return array();
            case "str_arr":
                return array(new COSString("Win"));
            case "null":
                return COSNull.NULL;
            case "ind_string":
                return new COSObject(new COSString("Acrobat"));
            case "ind_int":
                return new COSObject(COSInteger.get(7));
            case "ind_name_arr":
                return new COSObject(array(name("Win")));
            default:
                throw new IllegalArgumentException(caseName);
        }
    }

    static String keyForField(String field) {
        switch (field) {
            case "name":
                return "Name";
            case "date":
                return "Date";
            case "version":
                return "REx";
            case "revision":
                return "R";
            case "minrev":
                return "V";
            case "prerelease":
                return "PreRelease";
            case "os":
                return "OS";
            case "noefont":
                return "NonEFontNoWarn";
            case "trusted":
                return "TrustedMode";
            default:
                throw new IllegalArgumentException(field);
        }
    }

    static String projectField(PDPropBuildDataDict d, String field) {
        switch (field) {
            case "name":
                return nz(d.getName());
            case "date":
                return nz(d.getDate());
            case "version":
                return nz(d.getVersion());
            case "revision":
                return Long.toString(d.getRevision());
            case "minrev":
                return Long.toString(d.getMinimumRevision());
            case "prerelease":
                return Boolean.toString(d.getPreRelease());
            case "os":
                return nz(d.getOS());
            case "noefont":
                return Boolean.toString(d.getNonEFontNoWarn());
            case "trusted":
                return Boolean.toString(d.getTrustedMode());
            default:
                throw new IllegalArgumentException(field);
        }
    }

    static void runData(String field, String caseName) {
        COSDictionary dict = new COSDictionary();
        COSBase value = fieldValue(caseName);
        if (value != null) {
            dict.setItem(name(keyForField(field)), value);
        }
        PDPropBuildDataDict d = new PDPropBuildDataDict(dict);
        String result;
        try {
            result = projectField(d, field);
        } catch (Exception e) {
            result = "ERR:" + e.getClass().getSimpleName();
        }
        System.out.println("value=" + result);
    }

    public static void main(String[] args) {
        switch (args[0]) {
            case "build":
                runBuild(args[1]);
                break;
            case "data":
                runData(args[1], args[2]);
                break;
            default:
                throw new IllegalArgumentException(args[0]);
        }
    }
}
