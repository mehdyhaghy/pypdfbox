import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionHide;

/**
 * Live oracle probe for {@code PDActionHide} — the Hide action's {@code /H}
 * default and {@code /T} target accessor shape (single string vs annotation
 * dictionary vs array). {@code PDActionHide} was reachable only through the
 * generic ActionProbe with no dedicated coverage.
 *
 * No arguments. Output (UTF-8, LF-terminated "key=value" lines):
 *   empty.subtype=<getSubType-or-NULL>
 *   empty.h=<getH default>
 *   empty.t=<class-or-NULL>
 *   setFalse.h=false
 *   setStringT.t.class=COSString
 *   setStringT.t.value=field1
 *   setArrayT.t.class=COSArray
 *   setArrayT.t.size=2
 *   wire.keys=<sorted /Key list>
 */
public final class ActionHideTargetProbe {

    public static void main(String[] args) {
        PrintStream out = new PrintStream(System.out, true, java.nio.charset.StandardCharsets.UTF_8);

        PDActionHide e = new PDActionHide();
        out.println("empty.subtype=" + (e.getSubType() == null ? "NULL" : e.getSubType()));
        out.println("empty.h=" + e.getH());
        out.println("empty.t=" + (e.getT() == null ? "NULL" : e.getT().getClass().getSimpleName()));

        PDActionHide a = new PDActionHide();
        a.setH(false);
        out.println("setFalse.h=" + a.getH());

        PDActionHide st = new PDActionHide();
        st.setT(new COSString("field1"));
        out.println("setStringT.t.class=" + st.getT().getClass().getSimpleName());
        out.println("setStringT.t.value=" + ((COSString) st.getT()).getString());

        PDActionHide at = new PDActionHide();
        COSArray arr = new COSArray();
        arr.add(new COSString("f1"));
        arr.add(new COSString("f2"));
        at.setT(arr);
        out.println("setArrayT.t.class=" + at.getT().getClass().getSimpleName());
        out.println("setArrayT.t.size=" + ((COSArray) at.getT()).size());

        // wire form of a fully-populated hide action
        PDActionHide w = new PDActionHide();
        w.setH(true);
        w.setT(new COSString("widget"));
        COSDictionary cos = w.getCOSObject();
        java.util.TreeSet<String> keys = new java.util.TreeSet<>();
        for (COSName k : cos.keySet()) {
            keys.add(k.getName());
        }
        out.println("wire.keys=" + String.join(",", keys));
        out.println("wire.subtype=" + cos.getNameAsString(COSName.S));
    }
}
