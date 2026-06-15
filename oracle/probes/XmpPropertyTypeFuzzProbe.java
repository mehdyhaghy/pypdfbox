import java.io.PrintStream;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.type.BooleanType;
import org.apache.xmpbox.type.DateType;
import org.apache.xmpbox.type.IntegerType;
import org.apache.xmpbox.type.RealType;
import org.apache.xmpbox.type.TextType;

/**
 * Live oracle probe: construct each Apache xmpbox simple-property TYPE class with
 * a raw (often malformed) value and project the outcome.
 *
 * Usage: java -cp <xmpbox.jar>:<build> XmpPropertyTypeFuzzProbe <type> <raw>
 *
 *   <type> is one of: integer | real | boolean | text | date
 *   <raw>  is the raw STRING value handed to the constructor (which calls
 *          setValue under the hood). A handful of sentinel tokens select a
 *          non-string raw value so the instanceof branches can be exercised:
 *              __NULL__  -> null
 *
 * Output (one line, UTF-8, to stdout):
 *   OK<US>getValue<US>getStringValue          on success
 *   ERR<US>SimpleExceptionClassName           when the constructor/setValue throws
 *
 * where <US> is the ASCII unit separator (0x1f) so the payload may contain any
 * printable character including '|' or ','. getValue is rendered with
 * String.valueOf(...) which matches each boxed type's canonical toString
 * (Integer/Float/Boolean/String); DateType.getValue returns a Calendar which is
 * not used here (date getStringValue is the comparable surface).
 */
public final class XmpPropertyTypeFuzzProbe {
    private static final char US = (char) 0x1f;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String type = args[0];
        Object raw = decodeRaw(args.length > 1 ? args[1] : "");

        XMPMetadata meta = XMPMetadata.createXMPMetadata();
        String ns = "http://ns.example/";
        String prefix = "ex";
        String name = "p";

        try {
            switch (type) {
                case "integer": {
                    IntegerType t = new IntegerType(meta, ns, prefix, name, raw);
                    emitOk(out, String.valueOf(t.getValue()), t.getStringValue());
                    break;
                }
                case "real": {
                    RealType t = new RealType(meta, ns, prefix, name, raw);
                    emitOk(out, String.valueOf(t.getValue()), t.getStringValue());
                    break;
                }
                case "boolean": {
                    BooleanType t = new BooleanType(meta, ns, prefix, name, raw);
                    emitOk(out, String.valueOf(t.getValue()), t.getStringValue());
                    break;
                }
                case "text": {
                    TextType t = new TextType(meta, ns, prefix, name, raw);
                    emitOk(out, String.valueOf(t.getValue()), t.getStringValue());
                    break;
                }
                case "date": {
                    DateType t = new DateType(meta, ns, prefix, name, raw);
                    // DateType.getValue is a Calendar; getStringValue is the ISO
                    // 8601 rendering and is the comparable surface. Guard a null
                    // (empty/whitespace raw parses to a null Calendar upstream).
                    String sv = t.getStringValue();
                    emitOk(out, "<calendar>", sv == null ? "<null>" : sv);
                    break;
                }
                default:
                    out.print("ERR" + US + "UnknownType\n");
            }
        } catch (Throwable ex) {
            // Apache xmpbox throws IllegalArgumentException for bad simple-type
            // values; DateType wraps parse failures. Emit the simple class name.
            out.print("ERR" + US + ex.getClass().getSimpleName() + "\n");
        }
    }

    private static Object decodeRaw(String token) {
        if ("__NULL__".equals(token)) {
            return null;
        }
        return token;
    }

    private static void emitOk(PrintStream out, String value, String stringValue) {
        out.print("OK" + US + value + US + stringValue + "\n");
    }
}
