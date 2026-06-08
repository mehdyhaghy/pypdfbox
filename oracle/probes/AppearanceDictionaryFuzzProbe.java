import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;

/**
 * Direct malformed-input oracle for PDAppearanceDictionary,
 * PDAppearanceEntry, and PDAppearanceStream (PDFBox 3.0.7).
 */
public final class AppearanceDictionaryFuzzProbe {
    private static final COSName[] AP_KEYS = {COSName.N, COSName.R, COSName.D};

    private static COSObject indirect(COSBase value) {
        return new COSObject(value);
    }

    private static String hex(String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        StringBuilder sb = new StringBuilder();
        for (byte valueByte : bytes) {
            sb.append(String.format("%02x", valueByte & 0xff));
        }
        return sb.length() == 0 ? "empty" : sb.toString();
    }

    private static String message(Exception exception) {
        String value = exception.getMessage();
        return value == null ? exception.getClass().getSimpleName() : value.replace(' ', '_');
    }

    private static String entry(PDAppearanceEntry value) {
        if (value == null) {
            return "none";
        }
        StringBuilder sb = new StringBuilder(value.isStream() ? "stream" : "dict");
        sb.append(";as=");
        try {
            sb.append(value.getAppearanceStream() == null ? "none" : "stream");
        } catch (Exception exception) {
            sb.append("ERR:").append(message(exception));
        }
        sb.append(";sub=");
        try {
            Map<COSName, PDAppearanceStream> states = value.getSubDictionary();
            List<String> names = new ArrayList<>();
            for (COSName name : states.keySet()) {
                names.add(hex(name.getName()));
            }
            Collections.sort(names);
            sb.append(names.isEmpty() ? "empty" : String.join(",", names));
        } catch (Exception exception) {
            sb.append("ERR:").append(message(exception));
        }
        return sb.toString();
    }

    private static String raw(COSDictionary dictionary, COSName key) {
        COSBase value = dictionary.getItem(key);
        if (value == null) {
            return "absent";
        }
        if (value instanceof COSObject) {
            COSBase resolved = ((COSObject) value).getObject();
            return "indirect:" + (resolved == null ? "null" : resolved.getClass().getSimpleName());
        }
        return value.getClass().getSimpleName();
    }

    private static void emit(String name, PDAppearanceDictionary appearance) {
        COSDictionary dictionary = appearance.getCOSObject();
        System.out.println(
                "CASE " + name
                        + " n=" + entry(appearance.getNormalAppearance())
                        + " r=" + entry(appearance.getRolloverAppearance())
                        + " d=" + entry(appearance.getDownAppearance())
                        + " raw=" + raw(dictionary, AP_KEYS[0])
                        + "," + raw(dictionary, AP_KEYS[1])
                        + "," + raw(dictionary, AP_KEYS[2]));
    }

    private static void emitDictionaryCases() {
        emit("default", new PDAppearanceDictionary());
        emit("empty", new PDAppearanceDictionary(new COSDictionary()));

        COSBase[] values = {
            new COSStream(),
            new COSDictionary(),
            COSName.getPDFName("Bad"),
            COSNull.NULL,
            indirect(new COSStream()),
            indirect(new COSDictionary()),
            indirect(COSName.getPDFName("Bad")),
            indirect(COSNull.NULL)
        };
        String[] ids = {
            "stream", "dict", "scalar", "null", "istream", "idict", "iscalar", "inull"
        };
        for (int keyIndex = 0; keyIndex < AP_KEYS.length; keyIndex++) {
            for (int valueIndex = 0; valueIndex < values.length; valueIndex++) {
                COSDictionary dictionary = new COSDictionary();
                dictionary.setItem(COSName.N, new COSStream());
                dictionary.setItem(AP_KEYS[keyIndex], values[valueIndex]);
                emit(AP_KEYS[keyIndex].getName().toLowerCase() + "_" + ids[valueIndex],
                        new PDAppearanceDictionary(dictionary));
            }
        }

        COSDictionary states = new COSDictionary();
        states.setItem(COSName.getPDFName("On"), new COSStream());
        states.setItem(COSName.getPDFName("Indirect"), indirect(new COSStream()));
        states.setItem(COSName.getPDFName("Scalar"), COSInteger.get(4));
        states.setItem(COSName.getPDFName("Null"), COSNull.NULL);
        states.setItem(COSName.getPDFName("Dict"), new COSDictionary());
        states.setItem(COSName.getPDFName(""), new COSStream());
        states.setItem(COSName.getPDFName("A B"), new COSStream());
        states.setItem(COSName.getPDFName("A/B"), new COSStream());
        COSDictionary mixed = new COSDictionary();
        mixed.setItem(COSName.N, states);
        emit("states_mixed", new PDAppearanceDictionary(mixed));
    }

    private static void emitSetterCases() {
        PDAppearanceDictionary appearance = new PDAppearanceDictionary(new COSDictionary());
        COSStream normal = new COSStream();
        COSStream rollover = new COSStream();
        COSDictionary down = new COSDictionary();
        down.setItem(COSName.getPDFName("Pressed"), new COSStream());
        appearance.setNormalAppearance(new PDAppearanceEntry(normal));
        appearance.setRolloverAppearance(new PDAppearanceStream(rollover));
        appearance.setDownAppearance(new PDAppearanceEntry(down));
        emit("set_all", appearance);
        appearance.setNormalAppearance((PDAppearanceEntry) null);
        appearance.setRolloverAppearance((PDAppearanceEntry) null);
        appearance.setDownAppearance((PDAppearanceEntry) null);
        emit("set_clear", appearance);
    }

    private static String matrix(PDAppearanceStream stream) {
        java.awt.geom.AffineTransform value = stream.getMatrix().createAffineTransform();
        double[] matrix = new double[6];
        value.getMatrix(matrix);
        List<String> parts = new ArrayList<>();
        for (double component : matrix) {
            parts.add(component == Math.rint(component)
                    ? Long.toString((long) component) : Double.toString(component));
        }
        return String.join(",", parts);
    }

    private static void emitStream(String name, COSStream dictionary) {
        PDAppearanceStream stream = new PDAppearanceStream(dictionary);
        System.out.println(
                "STREAM " + name
                        + " type=" + dictionary.getNameAsString(COSName.TYPE)
                        + " subtype=" + dictionary.getNameAsString(COSName.SUBTYPE)
                        + " form=" + stream.getFormType()
                        + " struct=" + stream.getStructParents()
                        + " bbox=" + (stream.getBBox() == null ? "none" : "rect")
                        + " matrix=" + matrix(stream)
                        + " resources=" + (stream.getResources() == null ? "none" : "dict"));
    }

    private static void emitStreamCases() {
        emitStream("default", new COSStream());

        COSStream malformed = new COSStream();
        malformed.setItem(COSName.FORMTYPE, COSName.getPDFName("Bad"));
        malformed.setItem(COSName.STRUCT_PARENTS, new COSFloat(4.75f));
        malformed.setItem(COSName.BBOX, COSName.getPDFName("Bad"));
        malformed.setItem(COSName.MATRIX, COSName.getPDFName("Bad"));
        malformed.setItem(COSName.RESOURCES, COSNull.NULL);
        emitStream("malformed", malformed);

        COSStream indirectValues = new COSStream();
        COSArray bbox = new COSArray();
        bbox.add(COSInteger.ZERO);
        bbox.add(COSInteger.ZERO);
        bbox.add(COSInteger.get(10));
        bbox.add(COSInteger.get(20));
        indirectValues.setItem(COSName.BBOX, indirect(bbox));
        indirectValues.setItem(COSName.RESOURCES, indirect(new COSDictionary()));
        emitStream("indirect", indirectValues);
    }

    public static void main(String[] args) {
        emitDictionaryCases();
        emitSetterCases();
        emitStreamCases();
    }
}
