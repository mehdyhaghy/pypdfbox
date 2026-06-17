import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.lang.reflect.Method;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdfwriter.COSWriter;
import org.apache.pdfbox.pdmodel.common.COSObjectable;
import org.apache.pdfbox.pdmodel.common.PDNumberTreeNode;

/**
 * Live oracle probe pinning how PDFBox pads a HALF-populated /Limits array.
 *
 * PDNumberTreeNode.setLowerLimit / setUpperLimit are private; they create the
 * two-slot /Limits array with {@code arr.add(null); arr.add(null);} and then
 * fill ONE slot, leaving the other as a Java {@code null} list element. This
 * probe reaches the private setters by reflection, sets exactly one limit, and
 * dumps:
 *   - the runtime type of each /Limits slot via get(0)/get(1) (Java null vs a
 *     COSBase subtype) -- "null" means the slot holds a literal Java null;
 *   - the exact serialized bytes of the /Limits array through COSWriter
 *     (array.accept(new COSWriter(baos))), so the token a null slot produces is
 *     observed byte-for-byte rather than inferred.
 *
 * pypdfbox pads with COSNull.NULL instead of a Java null; the parity target is
 * the SERIALIZED bytes (and getObject() resolution), not the raw list element.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> NumberTreeLimitsPadProbe
 */
public final class NumberTreeLimitsPadProbe {

    static final class IntVal implements COSObjectable {
        final COSInteger v;
        IntVal(COSBase b) { this.v = (COSInteger) b; }
        public COSBase getCOSObject() { return v; }
    }

    static final class IntNode extends PDNumberTreeNode {
        IntNode() { super(IntVal.class); }
        IntNode(COSDictionary d) { super(d, IntVal.class); }
        @Override protected COSObjectable convertCOSToPD(COSBase base) { return new IntVal(base); }
        @Override protected PDNumberTreeNode createChildNode(COSDictionary d) { return new IntNode(d); }
    }

    static String slotType(COSBase b) {
        // get(i) returns the raw list element WITHOUT COSNull->null resolution.
        if (b == null) {
            return "null";
        }
        if (b instanceof COSInteger) {
            return "COSInteger(" + ((COSInteger) b).longValue() + ")";
        }
        return b.getClass().getSimpleName();
    }

    static String objType(COSBase b) {
        // getObject(i) resolves COSNull -> null.
        if (b == null) {
            return "null";
        }
        if (b instanceof COSInteger) {
            return "COSInteger(" + ((COSInteger) b).longValue() + ")";
        }
        return b.getClass().getSimpleName();
    }

    static String toHex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) {
            sb.append(String.format("%02x", x & 0xff));
        }
        return sb.toString();
    }

    static void dump(PrintStream out, String label, COSDictionary node) throws Exception {
        out.println("# " + label);
        COSArray lim = node.getCOSArray(COSName.LIMITS);
        if (lim == null) {
            out.println("  Limits: absent");
            return;
        }
        out.println("  size=" + lim.size());
        out.println("  slot0.get=" + slotType(lim.get(0)));
        out.println("  slot1.get=" + slotType(lim.get(1)));
        out.println("  slot0.getObject=" + objType(lim.getObject(0)));
        out.println("  slot1.getObject=" + objType(lim.getObject(1)));
        lim.setDirect(true);
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter writer = new COSWriter(baos);
        lim.accept(writer);
        // COSWriter.visitFromArray emits a trailing EOL; trim it for a stable token.
        String hex = toHex(baos.toByteArray());
        out.println("  serialized=" + hex);
    }

    static void setOnly(IntNode node, String which, int value) throws Exception {
        Method m = PDNumberTreeNode.class.getDeclaredMethod(which, Integer.class);
        m.setAccessible(true);
        m.invoke(node, Integer.valueOf(value));
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        // 1. Set ONLY the lower limit (slot 1 stays the as-created null).
        IntNode lowerOnly = new IntNode();
        setOnly(lowerOnly, "setLowerLimit", 5);
        dump(out, "setLowerLimit only", lowerOnly.getCOSObject());

        // 2. Set ONLY the upper limit (slot 0 stays the as-created null).
        IntNode upperOnly = new IntNode();
        setOnly(upperOnly, "setUpperLimit", 9);
        dump(out, "setUpperLimit only", upperOnly.getCOSObject());

        // 3. Both set (control -- no null slot remains).
        IntNode both = new IntNode();
        setOnly(both, "setLowerLimit", 5);
        setOnly(both, "setUpperLimit", 9);
        dump(out, "setLowerLimit+setUpperLimit", both.getCOSObject());
    }
}
