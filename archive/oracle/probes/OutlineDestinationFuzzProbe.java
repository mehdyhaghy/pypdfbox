import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem;

/** Differential fuzz probe for PDOutlineItem destination resolution. */
public final class OutlineDestinationFuzzProbe {
    private static COSArray dest(COSBase page, String type) {
        COSArray array = new COSArray();
        array.add(page);
        array.add(COSName.getPDFName(type));
        return array;
    }

    private static COSDictionary item(String name, PDDocument document) {
        COSDictionary dictionary = new COSDictionary();
        if ("dest_integer".equals(name)) {
            dictionary.setItem(COSName.DEST, COSInteger.ONE);
        } else if ("dest_string".equals(name)) {
            dictionary.setItem(COSName.DEST, new COSString("missing"));
        } else if ("dest_empty_array".equals(name)) {
            dictionary.setItem(COSName.DEST, new COSArray());
        } else if ("dest_unknown_type".equals(name)) {
            dictionary.setItem(COSName.DEST, dest(COSInteger.ZERO, "Bogus"));
        } else if ("page_zero".equals(name)) {
            dictionary.setItem(COSName.DEST, dest(COSInteger.ZERO, "Fit"));
        } else if ("page_one".equals(name)) {
            dictionary.setItem(COSName.DEST, dest(COSInteger.ONE, "Fit"));
        } else if ("page_oob".equals(name)) {
            dictionary.setItem(COSName.DEST, dest(COSInteger.get(2), "Fit"));
        } else if ("page_negative".equals(name)) {
            dictionary.setItem(COSName.DEST, dest(COSInteger.get(-1), "Fit"));
        } else if ("page_float".equals(name)) {
            dictionary.setItem(COSName.DEST, dest(new COSFloat(1.9f), "Fit"));
        } else if ("page_direct".equals(name)) {
            dictionary.setItem(COSName.DEST,
                    dest(document.getPage(1).getCOSObject(), "Fit"));
        } else if ("action_page_one".equals(name)) {
            dictionary.setItem(COSName.A, goTo(COSInteger.ONE));
        } else if ("bad_dest_valid_action".equals(name)) {
            dictionary.setItem(COSName.DEST, dest(COSInteger.ZERO, "Bogus"));
            dictionary.setItem(COSName.A, goTo(COSInteger.ONE));
        } else if ("wrong_action".equals(name)) {
            dictionary.setItem(COSName.A, COSInteger.ONE);
        }
        return dictionary;
    }

    private static COSDictionary goTo(COSBase page) {
        COSDictionary action = new COSDictionary();
        action.setItem(COSName.S, COSName.getPDFName("GoTo"));
        action.setItem(COSName.D, dest(page, "Fit"));
        return action;
    }

    private static String destinationCell(PDOutlineItem item) {
        try {
            PDDestination destination = item.getDestination();
            return destination == null ? "null" : destination.getClass().getSimpleName();
        } catch (Throwable error) {
            return "ERR:" + error.getClass().getSimpleName();
        }
    }

    private static String pageCell(PDOutlineItem item, PDDocument document) {
        try {
            PDPage found = item.findDestinationPage(document);
            if (found == null) {
                return "null";
            }
            for (int i = 0; i < document.getNumberOfPages(); i++) {
                if (document.getPage(i).getCOSObject() == found.getCOSObject()) {
                    return Integer.toString(i);
                }
            }
            return "foreign";
        } catch (Throwable error) {
            return "ERR:" + error.getClass().getSimpleName();
        }
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String[] cases = {"none", "dest_integer", "dest_string", "dest_empty_array",
            "dest_unknown_type", "page_zero", "page_one", "page_oob", "page_negative",
            "page_float", "page_direct", "action_page_one", "bad_dest_valid_action",
            "wrong_action"};
        try (PDDocument document = new PDDocument()) {
            document.addPage(new PDPage());
            document.addPage(new PDPage());
            for (String name : cases) {
                PDOutlineItem item = new PDOutlineItem(item(name, document));
                out.println("CASE " + name + " dest=" + destinationCell(item)
                        + " page=" + pageCell(item, document));
            }
        }
    }
}
