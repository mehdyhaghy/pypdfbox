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
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitHeightDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitRectangleDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitWidthDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageXYZDestination;

/**
 * Differential fuzz probe for the whole PDDestination family (wave 1539).
 *
 * Runs PDDestination.create() over ~30 malformed / edge-case destination
 * inputs and projects the observable surface as deterministic key=value lines:
 *   - the concrete Java wrapper class chosen (getClass().getSimpleName());
 *   - getPageNumber() / retrievePageNumber();
 *   - the type-name string at /D[1];
 *   - every coordinate getter appropriate to the concrete class
 *     (getLeft/getTop/getZoom/getRight/getBottom) — the upstream int/float
 *     -1 sentinel is emitted verbatim so the language boundary stays honest;
 *   - for named destinations, getNamedDestination();
 *   - the exact exception class name on the malformed-array fall-through.
 *
 * Output is consumed line-by-line by the Python parity test; each emitted
 * line is "<case>=<value>".
 */
public final class DestinationFuzzProbe {

    private static COSArray array(COSBase... values) {
        COSArray out = new COSArray();
        for (COSBase value : values) {
            out.add(value);
        }
        return out;
    }

    private static COSName n(String s) {
        return COSName.getPDFName(s);
    }

    private static String coords(PDPageDestination dest) {
        StringBuilder sb = new StringBuilder();
        if (dest instanceof PDPageXYZDestination) {
            PDPageXYZDestination d = (PDPageXYZDestination) dest;
            sb.append("left=").append(d.getLeft())
              .append(",top=").append(d.getTop())
              .append(",zoom=").append(d.getZoom());
        } else if (dest instanceof PDPageFitRectangleDestination) {
            PDPageFitRectangleDestination d = (PDPageFitRectangleDestination) dest;
            sb.append("left=").append(d.getLeft())
              .append(",bottom=").append(d.getBottom())
              .append(",right=").append(d.getRight())
              .append(",top=").append(d.getTop());
        } else if (dest instanceof PDPageFitWidthDestination) {
            sb.append("top=").append(((PDPageFitWidthDestination) dest).getTop());
        } else if (dest instanceof PDPageFitHeightDestination) {
            sb.append("left=").append(((PDPageFitHeightDestination) dest).getLeft());
        } else {
            sb.append("none");
        }
        return sb.toString();
    }

    private static void run(String name, COSBase base) {
        try {
            PDDestination dest = PDDestination.create(base);
            if (dest == null) {
                System.out.println(name + "=null");
            } else if (dest instanceof PDNamedDestination) {
                System.out.println(name + "=class:PDNamedDestination;value:"
                        + ((PDNamedDestination) dest).getNamedDestination());
            } else {
                PDPageDestination page = (PDPageDestination) dest;
                String type;
                try {
                    type = page.getCOSObject().getName(1);
                } catch (Exception e) {
                    type = "<exc:" + e.getClass().getSimpleName() + ">";
                }
                int retrieve;
                try {
                    retrieve = page.retrievePageNumber();
                } catch (Exception e) {
                    retrieve = -2;
                }
                System.out.println(name + "=class:" + dest.getClass().getSimpleName()
                        + ";page:" + page.getPageNumber()
                        + ";retrieve:" + retrieve
                        + ";type:" + type
                        + ";" + coords(page));
            }
        } catch (Exception e) {
            System.out.println(name + "=ERR:" + e.getClass().getSimpleName());
        }
    }

    public static void main(String[] args) {
        // --- base-type dispatch ------------------------------------------
        run("null_base", null);
        run("name_base", n("ChapterOne"));
        run("string_base", new COSString("Chapter Two"));
        run("integer_base", COSInteger.get(9));
        run("float_base", new COSFloat(1.5f));

        // --- malformed arrays --------------------------------------------
        run("empty_array", array());
        run("one_element_int", array(COSInteger.get(0)));
        run("one_element_name", array(n("Fit")));
        run("type_slot_string", array(COSInteger.get(0), new COSString("Fit")));
        run("type_slot_int", array(COSInteger.get(0), COSInteger.get(5)));
        run("type_slot_null", array(COSInteger.get(0), COSNull.NULL));

        // --- every fit-mode keyword --------------------------------------
        run("xyz", array(COSInteger.get(3), n("XYZ"),
                COSInteger.get(10), COSInteger.get(20), new COSFloat(1.5f)));
        run("fit", array(COSInteger.get(3), n("Fit")));
        run("fith", array(COSInteger.get(3), n("FitH"), COSInteger.get(700)));
        run("fitv", array(COSInteger.get(3), n("FitV"), COSInteger.get(72)));
        run("fitr", array(COSInteger.get(3), n("FitR"),
                COSInteger.get(1), COSInteger.get(2), COSInteger.get(3), COSInteger.get(4)));
        run("fitb", array(COSInteger.get(3), n("FitB")));
        run("fitbh", array(COSInteger.get(3), n("FitBH"), COSInteger.get(700)));
        run("fitbv", array(COSInteger.get(3), n("FitBV"), COSInteger.get(72)));
        run("unknown_type", array(COSInteger.get(0), n("Bogus")));

        // --- page-slot variants ------------------------------------------
        run("page_float", array(new COSFloat(3.9f), n("Fit")));
        run("page_null", array(COSNull.NULL, n("Fit")));
        run("page_name", array(n("NotAPage"), n("Fit")));
        run("page_string", array(new COSString("p"), n("Fit")));
        run("page_negative", array(COSInteger.get(-5), n("Fit")));

        // --- coordinate operand fuzz -------------------------------------
        run("xyz_missing_coords", array(COSInteger.get(0), n("XYZ")));
        run("xyz_short_one_coord", array(COSInteger.get(0), n("XYZ"), COSInteger.get(10)));
        run("xyz_null_coords", array(COSInteger.get(0), n("XYZ"),
                COSNull.NULL, COSNull.NULL, COSNull.NULL));
        run("xyz_name_coord", array(COSInteger.get(0), n("XYZ"),
                n("Garbage"), COSInteger.get(20), new COSFloat(1.5f)));
        run("xyz_string_coord", array(COSInteger.get(0), n("XYZ"),
                new COSString("x"), COSInteger.get(20), new COSFloat(1.5f)));
        run("xyz_zoom_zero", array(COSInteger.get(0), n("XYZ"),
                COSInteger.get(10), COSInteger.get(20), COSInteger.get(0)));
        run("xyz_extra_operands", array(COSInteger.get(0), n("XYZ"),
                COSInteger.get(10), COSInteger.get(20), new COSFloat(1.5f),
                COSInteger.get(99), COSInteger.get(100)));
        run("fith_missing_coord", array(COSInteger.get(0), n("FitH")));
        run("fith_null_coord", array(COSInteger.get(0), n("FitH"), COSNull.NULL));
        run("fitr_short", array(COSInteger.get(0), n("FitR"),
                COSInteger.get(1), COSInteger.get(2)));
        run("fitr_null_edges", array(COSInteger.get(0), n("FitR"),
                COSNull.NULL, COSNull.NULL, COSNull.NULL, COSNull.NULL));
    }
}
