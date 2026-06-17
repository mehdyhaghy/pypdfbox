import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/** Malformed PDRectangle(COSArray) construction + accessor oracle for wave 1524. */
public final class RectangleFuzzProbe {
    private static final String[] CASE_IDS = {
        "empty", "one", "two", "three", "four", "five", "six",
        "name0", "str1", "null2", "name_all",
        "rev_x", "rev_y", "rev_both", "neg", "negrev",
        "mix_if", "float_only", "int_only",
        "huge_urx", "huge_neg_llx", "huge_all",
        "zero_area", "line_x", "line_y",
        "indirect_slot", "indirect_null_slot", "indirect_name_slot",
        "frac"
    };

    private RectangleFuzzProbe() {}

    private static COSObject indirect(COSBase value) {
        return new COSObject(value);
    }

    private static COSArray build(String caseId) {
        COSArray array = new COSArray();
        switch (caseId) {
            case "empty":
                break;
            case "one":
                array.add(COSInteger.get(5));
                break;
            case "two":
                array.add(COSInteger.get(5));
                array.add(COSInteger.get(6));
                break;
            case "three":
                array.add(COSInteger.get(5));
                array.add(COSInteger.get(6));
                array.add(COSInteger.get(7));
                break;
            case "four":
                array.add(COSInteger.get(1));
                array.add(COSInteger.get(2));
                array.add(COSInteger.get(3));
                array.add(COSInteger.get(4));
                break;
            case "five":
                array.add(COSInteger.get(1));
                array.add(COSInteger.get(2));
                array.add(COSInteger.get(3));
                array.add(COSInteger.get(4));
                array.add(COSInteger.get(99));
                break;
            case "six":
                array.add(COSInteger.get(1));
                array.add(COSInteger.get(2));
                array.add(COSInteger.get(3));
                array.add(COSInteger.get(4));
                array.add(COSInteger.get(88));
                array.add(COSInteger.get(99));
                break;
            case "name0":
                array.add(COSName.getPDFName("Bad"));
                array.add(COSInteger.get(2));
                array.add(COSInteger.get(3));
                array.add(COSInteger.get(4));
                break;
            case "str1":
                array.add(COSInteger.get(1));
                array.add(new COSString("nope"));
                array.add(COSInteger.get(3));
                array.add(COSInteger.get(4));
                break;
            case "null2":
                array.add(COSInteger.get(1));
                array.add(COSInteger.get(2));
                array.add(COSNull.NULL);
                array.add(COSInteger.get(4));
                break;
            case "name_all":
                array.add(COSName.getPDFName("a"));
                array.add(COSName.getPDFName("b"));
                array.add(COSName.getPDFName("c"));
                array.add(COSName.getPDFName("d"));
                break;
            case "rev_x":
                array.add(COSInteger.get(400));
                array.add(COSInteger.get(100));
                array.add(COSInteger.get(50));
                array.add(COSInteger.get(300));
                break;
            case "rev_y":
                array.add(COSInteger.get(50));
                array.add(COSInteger.get(300));
                array.add(COSInteger.get(400));
                array.add(COSInteger.get(100));
                break;
            case "rev_both":
                array.add(COSInteger.get(400));
                array.add(COSInteger.get(300));
                array.add(COSInteger.get(50));
                array.add(COSInteger.get(100));
                break;
            case "neg":
                array.add(COSInteger.get(-100));
                array.add(COSInteger.get(-200));
                array.add(COSInteger.get(-50));
                array.add(COSInteger.get(-60));
                break;
            case "negrev":
                array.add(COSInteger.get(-50));
                array.add(COSInteger.get(-60));
                array.add(COSInteger.get(-100));
                array.add(COSInteger.get(-200));
                break;
            case "mix_if":
                array.add(COSInteger.get(1));
                array.add(new COSFloat(2.5f));
                array.add(COSInteger.get(3));
                array.add(new COSFloat(4.5f));
                break;
            case "float_only":
                array.add(new COSFloat(1.25f));
                array.add(new COSFloat(2.5f));
                array.add(new COSFloat(7.75f));
                array.add(new COSFloat(8.5f));
                break;
            case "int_only":
                array.add(COSInteger.get(10));
                array.add(COSInteger.get(20));
                array.add(COSInteger.get(30));
                array.add(COSInteger.get(40));
                break;
            case "huge_urx":
                array.add(COSInteger.get(0));
                array.add(COSInteger.get(0));
                array.add(new COSFloat(5.0e9f));
                array.add(COSInteger.get(100));
                break;
            case "huge_neg_llx":
                // urx = 0 so width = 0 - (-clamp) = clamp exactly in both
                // float32 (upstream) and float64 (pypdfbox); a non-zero urx
                // here would expose the float-vs-double width cliff.
                array.add(new COSFloat(-5.0e9f));
                array.add(COSInteger.get(0));
                array.add(COSInteger.get(0));
                array.add(COSInteger.get(100));
                break;
            case "huge_all":
                array.add(new COSFloat(-9.0e9f));
                array.add(new COSFloat(-9.0e9f));
                array.add(new COSFloat(9.0e9f));
                array.add(new COSFloat(9.0e9f));
                break;
            case "zero_area":
                array.add(COSInteger.get(5));
                array.add(COSInteger.get(5));
                array.add(COSInteger.get(5));
                array.add(COSInteger.get(5));
                break;
            case "line_x":
                array.add(COSInteger.get(5));
                array.add(COSInteger.get(5));
                array.add(COSInteger.get(5));
                array.add(COSInteger.get(20));
                break;
            case "line_y":
                array.add(COSInteger.get(5));
                array.add(COSInteger.get(5));
                array.add(COSInteger.get(20));
                array.add(COSInteger.get(5));
                break;
            case "indirect_slot":
                array.add(indirect(COSInteger.get(1)));
                array.add(COSInteger.get(2));
                array.add(indirect(new COSFloat(3.5f)));
                array.add(COSInteger.get(4));
                break;
            case "indirect_null_slot":
                array.add(COSInteger.get(1));
                array.add(indirect(null));
                array.add(COSInteger.get(3));
                array.add(COSInteger.get(4));
                break;
            case "indirect_name_slot":
                array.add(COSInteger.get(1));
                array.add(COSInteger.get(2));
                array.add(indirect(COSName.getPDFName("Bad")));
                array.add(COSInteger.get(4));
                break;
            case "frac":
                array.add(new COSFloat(1.1f));
                array.add(new COSFloat(2.2f));
                array.add(new COSFloat(3.3f));
                array.add(new COSFloat(4.4f));
                break;
            default:
                throw new IllegalArgumentException(caseId);
        }
        return array;
    }

    private static String number(float value) {
        if (value == (long) value) {
            return Long.toString((long) value);
        }
        return String.format(Locale.ROOT, "%.4f", value);
    }

    private static String project(String caseId) {
        StringBuilder result = new StringBuilder("CASE ").append(caseId);
        try {
            PDRectangle rect = new PDRectangle(build(caseId));
            result.append(" llx=").append(number(rect.getLowerLeftX()));
            result.append(" lly=").append(number(rect.getLowerLeftY()));
            result.append(" urx=").append(number(rect.getUpperRightX()));
            result.append(" ury=").append(number(rect.getUpperRightY()));
            result.append(" w=").append(number(rect.getWidth()));
            result.append(" h=").append(number(rect.getHeight()));
            // contains: a probe point near the centre of the *normalized* box.
            float cx = (rect.getLowerLeftX() + rect.getUpperRightX()) / 2.0f;
            float cy = (rect.getLowerLeftY() + rect.getUpperRightY()) / 2.0f;
            result.append(" cin=").append(rect.contains(cx, cy));
            result.append(" cout=").append(rect.contains(cx, cy - 1.0e6f));
            PDRectangle re = rect.createRetranslatedRectangle();
            result.append(" re=").append(number(re.getLowerLeftX()))
                    .append(",").append(number(re.getLowerLeftY()))
                    .append(",").append(number(re.getUpperRightX()))
                    .append(",").append(number(re.getUpperRightY()));
            result.append(" ca=").append(re.getCOSArray().size());
        } catch (RuntimeException exception) {
            result.append(" err=").append(exception.getClass().getSimpleName());
        }
        return result.toString();
    }

    public static void main(String[] args) {
        for (String caseId : CASE_IDS) {
            System.out.println(project(caseId));
        }
    }
}
