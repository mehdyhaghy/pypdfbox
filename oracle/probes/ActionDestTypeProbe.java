import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionGoTo;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;

/**
 * Live oracle probe: pin the TYPE CONTRACT of PDActionGoTo.getDestination()
 * across the four /D shapes the PDF spec allows for a GoTo action's
 * destination (PDF 32000-1 §12.6.4.2):
 *
 *   stringnamed   /D = COSString("Chapter1")     -> named destination
 *   namenamed     /D = COSName("Chapter2")       -> named destination
 *   array         /D = [<page> /XYZ ...]         -> explicit page target
 *   dictbad       /D = COSDictionary{}           -> malformed (neither)
 *
 * Upstream PDActionGoTo.getDestination() is a one-liner:
 *   return PDDestination.create(getCOSObject().getDictionaryObject(COSName.D));
 * so the dispatch is entirely PDDestination.create's: COSString / COSName ->
 * PDNamedDestination; a recognised array -> the concrete page-destination
 * subclass; an unrecognised shape -> IOException.
 *
 * Output (UTF-8, LF-terminated), one line per shape:
 *   <label>\t<javaSimpleClassName>\t<payload>
 * where javaSimpleClassName is getClass().getSimpleName() of the returned
 * PDDestination (or "null" / "EXC:<ExceptionType>"), and payload is the
 * named-destination string for PDNamedDestination (empty otherwise). This pins
 * the Python port's get_destination() dispatch against Java's class identity.
 */
public final class ActionDestTypeProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();

        sb.append(line("stringnamed", makeAction(new COSString("Chapter1"))));
        sb.append(line("namenamed", makeAction(COSName.getPDFName("Chapter2"))));

        COSArray arr = new COSArray();
        COSDictionary page = new COSDictionary();
        page.setName(COSName.TYPE, "Page");
        arr.add(page);
        arr.add(COSName.getPDFName("XYZ"));
        sb.append(line("array", makeAction(arr)));

        sb.append(line("dictbad", makeAction(new COSDictionary())));

        out.print(sb);
    }

    private static PDActionGoTo makeAction(org.apache.pdfbox.cos.COSBase d) {
        PDActionGoTo action = new PDActionGoTo();
        action.getCOSObject().setItem(COSName.D, d);
        return action;
    }

    private static String line(String label, PDActionGoTo action) {
        String typeName;
        String payload = "";
        try {
            PDDestination dest = action.getDestination();
            if (dest == null) {
                typeName = "null";
            } else {
                typeName = dest.getClass().getSimpleName();
                if (dest instanceof org.apache.pdfbox.pdmodel.interactive
                        .documentnavigation.destination.PDNamedDestination) {
                    String n = ((org.apache.pdfbox.pdmodel.interactive
                            .documentnavigation.destination.PDNamedDestination) dest)
                            .getNamedDestination();
                    payload = n == null ? "" : n;
                }
            }
        } catch (Exception e) {
            typeName = "EXC:" + e.getClass().getSimpleName();
        }
        return label + "\t" + typeName + "\t" + payload + "\n";
    }
}
