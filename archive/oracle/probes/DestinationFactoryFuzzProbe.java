import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDNamedDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;

/** Differential destination factory/read probe over malformed arrays (wave 1518). */
public final class DestinationFactoryFuzzProbe {
    private static COSArray array(COSBase... values) {
        COSArray out = new COSArray();
        for (COSBase value : values) {
            out.add(value);
        }
        return out;
    }

    private static void run(String name, COSBase base) {
        try {
            PDDestination dest = PDDestination.create(base);
            if (dest == null) {
                System.out.println("CASE " + name + " null");
            } else if (dest instanceof PDNamedDestination) {
                System.out.println("CASE " + name + " class=PDNamedDestination value="
                        + ((PDNamedDestination) dest).getNamedDestination());
            } else {
                PDPageDestination page = (PDPageDestination) dest;
                System.out.println("CASE " + name + " class="
                        + dest.getClass().getSimpleName() + " page=" + page.getPageNumber()
                        + " retrieve=" + page.retrievePageNumber() + " type="
                        + page.getCOSObject().getName(1));
            }
        } catch (Exception e) {
            System.out.println("CASE " + name + " ERR:" + e.getClass().getSimpleName());
        }
    }

    public static void main(String[] args) {
        run("null", null);
        run("named_name", COSName.getPDFName("ChapterOne"));
        run("named_string", new COSString("Chapter Two"));
        run("fit", array(COSInteger.get(3), COSName.getPDFName("Fit")));
        run("fitb", array(COSInteger.get(3), COSName.getPDFName("FitB")));
        run("fith", array(COSInteger.get(3), COSName.getPDFName("FitH"), COSInteger.get(10)));
        run("fitbh", array(COSInteger.get(3), COSName.getPDFName("FitBH"), COSInteger.get(10)));
        run("fitv", array(COSInteger.get(3), COSName.getPDFName("FitV"), COSInteger.get(10)));
        run("fitbv", array(COSInteger.get(3), COSName.getPDFName("FitBV"), COSInteger.get(10)));
        run("fitr", array(COSInteger.get(3), COSName.getPDFName("FitR"),
                COSInteger.get(1), COSInteger.get(2), COSInteger.get(3), COSInteger.get(4)));
        run("xyz", array(COSInteger.get(3), COSName.getPDFName("XYZ"),
                COSInteger.get(1), COSInteger.get(2), COSInteger.get(3)));
        run("float_page", array(new COSFloat(3.9f), COSName.getPDFName("Fit")));
        run("null_page", array(COSNull.NULL, COSName.getPDFName("Fit")));
        run("unknown_type", array(COSInteger.get(0), COSName.getPDFName("Bogus")));
        run("short_empty", array());
        run("short_one", array(COSInteger.get(0)));
        run("wrong_type_slot", array(COSInteger.get(0), new COSString("Fit")));
        run("wrong_base", COSInteger.get(9));
    }
}
