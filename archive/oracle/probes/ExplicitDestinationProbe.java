import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageXYZDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitWidthDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitHeightDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitRectangleDestination;

/**
 * Live oracle probe for the explicit page-destination family.
 * Emits deterministic key=value lines for:
 *  - null-slot getter sentinels (getLeft/getTop/getZoom == -1 on a fresh XYZ)
 *  - setter(-1) -> COSNull slot; round-trip array shape
 *  - int truncation of getLeft/getTop vs float getZoom
 *  - getPageNumber / setPageNumber duality
 *  - PDDestination.create dispatch + exact exception messages for malformed arrays
 */
public class ExplicitDestinationProbe
{
    static String dumpArray(COSArray a)
    {
        StringBuilder sb = new StringBuilder();
        sb.append("[");
        for (int i = 0; i < a.size(); i++)
        {
            if (i > 0) sb.append(",");
            COSBase o = a.getObject(i);
            if (o instanceof COSNull) sb.append("null");
            else if (o instanceof COSName) sb.append("/" + ((COSName) o).getName());
            else if (o instanceof COSInteger) sb.append("int:" + ((COSInteger) o).intValue());
            else if (o instanceof COSFloat) sb.append("float:" + ((COSFloat) o).floatValue());
            else sb.append(o == null ? "<absent>" : o.getClass().getSimpleName());
        }
        sb.append("]");
        return sb.toString();
    }

    public static void main(String[] args) throws Exception
    {
        // 1. Fresh XYZ defaults -> all slots null, getters return -1.
        PDPageXYZDestination xyz = new PDPageXYZDestination();
        System.out.println("xyz_fresh_array=" + dumpArray(xyz.getCOSObject()));
        System.out.println("xyz_fresh_getLeft=" + xyz.getLeft());
        System.out.println("xyz_fresh_getTop=" + xyz.getTop());
        System.out.println("xyz_fresh_getZoom=" + xyz.getZoom());

        // 2. setLeft/Top with float-ish ints + zoom float; int truncation.
        xyz.setLeft(72);
        xyz.setTop(540);
        xyz.setZoom(1.5f);
        System.out.println("xyz_set_array=" + dumpArray(xyz.getCOSObject()));
        System.out.println("xyz_set_getLeft=" + xyz.getLeft());
        System.out.println("xyz_set_getTop=" + xyz.getTop());
        System.out.println("xyz_set_getZoom=" + xyz.getZoom());

        // 3. setLeft(-1) -> COSNull; setZoom(-1) -> COSNull.
        xyz.setLeft(-1);
        xyz.setZoom(-1f);
        System.out.println("xyz_unset_array=" + dumpArray(xyz.getCOSObject()));
        System.out.println("xyz_unset_getLeft=" + xyz.getLeft());
        System.out.println("xyz_unset_getZoom=" + xyz.getZoom());

        // 4. setZoom(0) -> explicit 0, getZoom == 0.0 (not -1).
        PDPageXYZDestination xyz2 = new PDPageXYZDestination();
        xyz2.setZoom(0f);
        System.out.println("xyz_zoom0_array=" + dumpArray(xyz2.getCOSObject()));
        System.out.println("xyz_zoom0_getZoom=" + xyz2.getZoom());

        // 5. Short array (2 elements) getters.
        COSArray shortArr = new COSArray();
        shortArr.add(COSInteger.get(0));
        shortArr.add(COSName.getPDFName("XYZ"));
        PDPageXYZDestination xyzShort = new PDPageXYZDestination(shortArr);
        System.out.println("xyz_short_getLeft=" + xyzShort.getLeft());
        System.out.println("xyz_short_getTop=" + xyzShort.getTop());
        try { System.out.println("xyz_short_getZoom=" + xyzShort.getZoom()); }
        catch (Exception e) { System.out.println("xyz_short_getZoom_exc=" + e.getClass().getSimpleName()); }

        // 6. getPageNumber / setPageNumber duality.
        PDPageXYZDestination xyzPage = new PDPageXYZDestination();
        System.out.println("pagenum_default=" + xyzPage.getPageNumber());
        xyzPage.setPageNumber(7);
        System.out.println("pagenum_set=" + xyzPage.getPageNumber());
        System.out.println("pagenum_array0=" + dumpArray(xyzPage.getCOSObject()).split(",")[0]);

        // 7. Fresh Fit / FitR / FitH / FitV array shapes.
        System.out.println("fit_fresh_array=" + dumpArray(new PDPageFitDestination().getCOSObject()));
        System.out.println("fitw_fresh_array=" + dumpArray(new PDPageFitWidthDestination().getCOSObject()));
        System.out.println("fith_fresh_array=" + dumpArray(new PDPageFitHeightDestination().getCOSObject()));
        System.out.println("fitr_fresh_array=" + dumpArray(new PDPageFitRectangleDestination().getCOSObject()));

        // 8. FitR 4-coordinate accessors + setLeft(-1) null slot.
        PDPageFitRectangleDestination fitr = new PDPageFitRectangleDestination();
        fitr.setLeft(10); fitr.setBottom(20); fitr.setRight(110); fitr.setTop(220);
        System.out.println("fitr_set_array=" + dumpArray(fitr.getCOSObject()));
        System.out.println("fitr_getLeft=" + fitr.getLeft());
        System.out.println("fitr_getBottom=" + fitr.getBottom());
        System.out.println("fitr_getRight=" + fitr.getRight());
        System.out.println("fitr_getTop=" + fitr.getTop());
        fitr.setLeft(-1);
        System.out.println("fitr_unset_array=" + dumpArray(fitr.getCOSObject()));
        System.out.println("fitr_unset_getLeft=" + fitr.getLeft());

        // 9. create() dispatch + malformed messages.
        COSArray xyzArr = new COSArray();
        xyzArr.add(COSInteger.get(0));
        xyzArr.add(COSName.getPDFName("XYZ"));
        System.out.println("create_xyz=" + PDDestination.create(xyzArr).getClass().getSimpleName());

        COSArray fitbArr = new COSArray();
        fitbArr.add(COSInteger.get(0));
        fitbArr.add(COSName.getPDFName("FitB"));
        System.out.println("create_fitb=" + PDDestination.create(fitbArr).getClass().getSimpleName());

        COSArray fitbhArr = new COSArray();
        fitbhArr.add(COSInteger.get(0));
        fitbhArr.add(COSName.getPDFName("FitBH"));
        System.out.println("create_fitbh=" + PDDestination.create(fitbhArr).getClass().getSimpleName());

        COSArray fitbvArr = new COSArray();
        fitbvArr.add(COSInteger.get(0));
        fitbvArr.add(COSName.getPDFName("FitBV"));
        System.out.println("create_fitbv=" + PDDestination.create(fitbvArr).getClass().getSimpleName());

        // Unknown tag.
        COSArray fooArr = new COSArray();
        fooArr.add(COSInteger.get(0));
        fooArr.add(COSName.getPDFName("Foo"));
        try { PDDestination.create(fooArr); System.out.println("create_foo=NO_THROW"); }
        catch (Exception e) { System.out.println("create_foo_msg=" + e.getMessage()); }

        // Short array (size 1) -> falls through to else -> can't convert.
        COSArray tooShort = new COSArray();
        tooShort.add(COSInteger.get(0));
        try { Object r = PDDestination.create(tooShort); System.out.println("create_short=" + (r == null ? "null" : r.getClass().getSimpleName())); }
        catch (Exception e) { System.out.println("create_short_msg=" + e.getMessage()); }

        // size 0 -> falls through to else.
        COSArray empty = new COSArray();
        try { Object r = PDDestination.create(empty); System.out.println("create_empty=" + (r == null ? "null" : r.getClass().getSimpleName())); }
        catch (Exception e) { System.out.println("create_empty_msg=" + e.getMessage()); }

        // item[1] not a name (an integer) -> falls through to else.
        COSArray nonName = new COSArray();
        nonName.add(COSInteger.get(0));
        nonName.add(COSInteger.get(5));
        try { Object r = PDDestination.create(nonName); System.out.println("create_nonname=" + (r == null ? "null" : r.getClass().getSimpleName())); }
        catch (Exception e) { System.out.println("create_nonname_msg=" + e.getMessage()); }

        // null -> null.
        System.out.println("create_null=" + PDDestination.create(null));
    }
}
