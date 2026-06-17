import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSString;

/**
 * Second-wave malformed-input fuzz for linearization parameter dictionary access.
 * Complements LinearizationDictionaryFuzzProbe (wave 1519) with angles it did not
 * cover: boolean / name / float markers, zero / negative float markers, mixed and
 * degenerate /H arrays, huge float coords (saturating intValue narrowing), and
 * negative numeric coords.
 */
public final class LinearizationDictFuzzProbe {
    private static COSName n(String value) {
        return COSName.getPDFName(value);
    }

    private static COSArray arr(COSBase... values) {
        COSArray array = new COSArray();
        for (COSBase value : values) {
            array.add(value);
        }
        return array;
    }

    private static COSDictionary dict(String name) {
        COSDictionary d = new COSDictionary();
        if ("bool_true_marker".equals(name)) {
            d.setItem(n("Linearized"), COSBoolean.TRUE);
        } else if ("bool_false_marker".equals(name)) {
            d.setItem(n("Linearized"), COSBoolean.FALSE);
        } else if ("name_marker".equals(name)) {
            d.setItem(n("Linearized"), n("One"));
        } else if ("float_one_marker".equals(name)) {
            d.setItem(n("Linearized"), new COSFloat(1.0f));
            d.setItem(n("L"), COSInteger.get(500));
        } else if ("float_zero_marker".equals(name)) {
            d.setItem(n("Linearized"), new COSFloat(0.0f));
        } else if ("float_neg_marker".equals(name)) {
            d.setItem(n("Linearized"), new COSFloat(-2.5f));
        } else if ("name_coords".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("L"), n("Big"));
            d.setItem(n("O"), n("Seven"));
            d.setItem(n("E"), COSBoolean.TRUE);
            d.setItem(n("N"), new COSString("3"));
            d.setItem(n("T"), arr(COSInteger.ONE));
        } else if ("neg_coords".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("L"), COSInteger.get(-100));
            d.setItem(n("O"), COSInteger.get(-7));
            d.setItem(n("E"), COSInteger.get(-80));
            d.setItem(n("N"), COSInteger.get(-3));
            d.setItem(n("T"), COSInteger.get(-91));
        } else if ("mixed_h4".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("H"), arr(COSInteger.get(11), new COSFloat(22.9f),
                    COSInteger.get(33), new COSFloat(44.1f)));
        } else if ("empty_h".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("H"), new COSArray());
        } else if ("single_h".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("H"), arr(COSInteger.get(11)));
        } else if ("neg_h".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("H"), arr(COSInteger.get(-11), COSInteger.get(-22)));
        } else if ("bool_h_member".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("H"), arr(COSInteger.ONE, COSBoolean.TRUE));
        } else if ("nested_h_member".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("H"), arr(COSInteger.ONE, arr(COSInteger.TWO)));
        } else if ("huge_float_coords".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("L"), new COSFloat(3e38f));
            d.setItem(n("O"), new COSFloat(-3e38f));
            d.setItem(n("H"), arr(new COSFloat(3e38f), new COSFloat(-3e38f)));
        } else if ("marker_only".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
        } else if ("coords_no_marker".equals(name)) {
            d.setItem(n("L"), COSInteger.get(100));
            d.setItem(n("N"), COSInteger.get(3));
        } else if ("huge_marker".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.get(2147483648L));
        }
        return d;
    }

    private static String intCell(COSDictionary d, String key) {
        return Integer.toString(d.getInt(key));
    }

    private static String hintOrAbsent(COSDictionary d) {
        COSBase value = d.getDictionaryObject(n("H"));
        if (!(value instanceof COSArray)) {
            return "absent";
        }
        COSArray array = (COSArray) value;
        if (array.size() != 2 && array.size() != 4) {
            return "absent";
        }
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < array.size(); i++) {
            COSBase item = array.getObject(i);
            if (!(item instanceof COSNumber)) {
                return "absent";
            }
            if (i > 0) {
                builder.append(',');
            }
            builder.append(((COSNumber) item).intValue());
        }
        return builder.toString();
    }

    private static String linearized(COSDictionary d) {
        COSBase value = d.getDictionaryObject(n("Linearized"));
        if (value instanceof COSNumber) {
            return ((COSNumber) value).floatValue() != 0f ? "true" : "false";
        }
        return "false";
    }

    private static String version(COSDictionary d) {
        COSBase value = d.getDictionaryObject(n("Linearized"));
        if (value instanceof COSNumber) {
            return Float.toString(((COSNumber) value).floatValue());
        }
        return "0.0";
    }

    private static void emit(PrintStream out, String name) {
        COSDictionary d = dict(name);
        out.println("CASE " + name
                + " linearized=" + linearized(d)
                + " version=" + version(d)
                + " L=" + intCell(d, "L")
                + " O=" + intCell(d, "O")
                + " E=" + intCell(d, "E")
                + " N=" + intCell(d, "N")
                + " T=" + intCell(d, "T")
                + " H=" + hintOrAbsent(d));
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String[] cases = {"empty", "bool_true_marker", "bool_false_marker",
            "name_marker", "float_one_marker", "float_zero_marker",
            "float_neg_marker", "name_coords", "neg_coords", "mixed_h4",
            "empty_h", "single_h", "neg_h", "bool_h_member", "nested_h_member",
            "huge_float_coords", "marker_only", "coords_no_marker", "huge_marker"};
        for (String name : cases) {
            emit(out, name);
        }
    }
}
