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

/** Direct malformed-input fuzz for linearization parameter dictionary access. */
public final class LinearizationDictionaryFuzzProbe {
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
        if ("valid_ints".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("L"), COSInteger.get(100));
            d.setItem(n("O"), COSInteger.get(7));
            d.setItem(n("E"), COSInteger.get(80));
            d.setItem(n("N"), COSInteger.get(3));
            d.setItem(n("T"), COSInteger.get(91));
            d.setItem(n("H"), arr(COSInteger.get(11), COSInteger.get(22)));
        } else if ("valid_floats".equals(name)) {
            d.setItem(n("Linearized"), new COSFloat(1.5f));
            d.setItem(n("L"), new COSFloat(100.9f));
            d.setItem(n("O"), new COSFloat(7.9f));
            d.setItem(n("E"), new COSFloat(80.9f));
            d.setItem(n("N"), new COSFloat(3.9f));
            d.setItem(n("T"), new COSFloat(91.9f));
            d.setItem(n("H"), arr(new COSFloat(11.9f), new COSFloat(22.9f),
                    new COSFloat(33.9f), new COSFloat(44.9f)));
        } else if ("zero_marker".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ZERO);
        } else if ("negative_marker".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.get(-1));
        } else if ("string_marker".equals(name)) {
            d.setItem(n("Linearized"), new COSString("1"));
            d.setItem(n("L"), new COSString("100"));
            d.setItem(n("H"), new COSString("11 22"));
        } else if ("bad_h_size".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("H"), arr(COSInteger.ONE, COSInteger.TWO, COSInteger.THREE));
        } else if ("bad_h_member".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("H"), arr(COSInteger.ONE, new COSString("2")));
        } else if ("wrong_h_type".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("H"), COSName.getPDFName("Nope"));
        } else if ("huge_ints".equals(name)) {
            d.setItem(n("Linearized"), COSInteger.ONE);
            d.setItem(n("L"), COSInteger.get(2147483648L));
            d.setItem(n("O"), COSInteger.get(-2147483649L));
            d.setItem(n("H"), arr(COSInteger.get(2147483648L), COSInteger.get(-2147483649L)));
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
        String[] cases = {"empty", "valid_ints", "valid_floats", "zero_marker",
            "negative_marker", "string_marker", "bad_h_size", "bad_h_member",
            "wrong_h_type", "huge_ints"};
        for (String name : cases) {
            emit(out, name);
        }
    }
}
