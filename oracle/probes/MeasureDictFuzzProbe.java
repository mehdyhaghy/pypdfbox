import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.interactive.measurement.PDMeasureDictionary;
import org.apache.pdfbox.pdmodel.interactive.measurement.PDNumberFormatDictionary;
import org.apache.pdfbox.pdmodel.interactive.measurement.PDRectlinearMeasureDictionary;
import org.apache.pdfbox.pdmodel.interactive.measurement.PDViewportDictionary;

/**
 * Differential-fuzz probe for the measurement annotation dictionaries:
 * {@code PDMeasureDictionary}, {@code PDRectlinearMeasureDictionary},
 * {@code PDViewportDictionary}, {@code PDNumberFormatDictionary}.
 *
 * Complements the existing default/round-trip probes (NumberFormatDictionaryProbe,
 * RectlinearMeasureProbe, ViewportMeasureDispatchProbe) by hammering MALFORMED /
 * edge-case COS shapes through every accessor and projecting the result (and
 * exception class, if any). Angles not previously covered:
 *
 *   - /Subtype stored as COSName "RL" vs unknown name vs COSString "RL" vs
 *     COSInteger vs absent (get_subtype default + dispatch);
 *   - /X /Y /D /A /T /S as: proper array-of-dict, empty array, array with
 *     non-dict members mixed in, a bare COSDictionary (non-array), a COSInteger
 *     (non-array), absent — projecting list size or NULL;
 *   - /R scale ratio as COSString vs COSName vs COSInteger;
 *   - /O coord origin as float array vs mixed array vs non-array;
 *   - /CYX as int vs float vs string vs absent;
 *   - number-format /C as negative/zero/string, /D precision int vs float vs
 *     string, /F format name unknown/string/name, /U units as name vs string;
 *   - viewport /BBox arity (0/2/4/6 elements), /Name as name vs string vs int,
 *     /Measure non-dict, getMeasure dispatch.
 *
 * No arguments. Output (UTF-8, LF-terminated "key=value" lines).
 */
public final class MeasureDictFuzzProbe {

    private static String nz(Object v) {
        return v == null ? "NULL" : v.toString();
    }

    private static String sz(PDNumberFormatDictionary[] a) {
        return a == null ? "NULL" : "len:" + a.length;
    }

    private interface NfSupplier {
        PDNumberFormatDictionary[] get();
    }

    /** Project a list-getter call, capturing a thrown exception class instead. */
    private static String szTry(NfSupplier s) {
        try {
            return sz(s.get());
        } catch (RuntimeException e) {
            return e.getClass().getSimpleName();
        }
    }

    private static String farr(float[] a) {
        if (a == null) {
            return "NULL";
        }
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < a.length; i++) {
            if (i > 0) {
                sb.append(",");
            }
            sb.append(a[i]);
        }
        return sb.append("]").toString();
    }

    private static COSDictionary nfDict(String units) {
        COSDictionary d = new COSDictionary();
        d.setName(COSName.TYPE, "NumberFormat");
        if (units != null) {
            d.setString(COSName.getPDFName("U"), units);
        }
        return d;
    }

    public static void main(String[] args) {
        PrintStream out = new PrintStream(System.out, true, java.nio.charset.StandardCharsets.UTF_8);

        // ---- /Subtype shapes on a base measure dict ------------------------
        // RL name
        COSDictionary d1 = new COSDictionary();
        d1.setName(COSName.SUBTYPE, "RL");
        out.println("subtype.name_rl=" + new PDMeasureDictionary(d1).getSubtype());
        // unknown name
        COSDictionary d2 = new COSDictionary();
        d2.setName(COSName.SUBTYPE, "GEO");
        out.println("subtype.name_geo=" + new PDMeasureDictionary(d2).getSubtype());
        // string "RL"
        COSDictionary d3 = new COSDictionary();
        d3.setItem(COSName.SUBTYPE, new COSString("RL"));
        out.println("subtype.string_rl=" + new PDMeasureDictionary(d3).getSubtype());
        // integer subtype (wrong type)
        COSDictionary d4 = new COSDictionary();
        d4.setItem(COSName.SUBTYPE, COSInteger.get(7));
        out.println("subtype.int=" + new PDMeasureDictionary(d4).getSubtype());
        // absent
        out.println("subtype.absent=" + new PDMeasureDictionary(new COSDictionary()).getSubtype());

        // ---- rectlinear array getters over malformed /D --------------------
        PDRectlinearMeasureDictionary rl = new PDRectlinearMeasureDictionary();
        COSDictionary rld = rl.getCOSObject();

        // proper array of 2 dicts
        COSArray good = new COSArray();
        good.add(nfDict("mi"));
        good.add(nfDict("km"));
        rld.setItem(COSName.getPDFName("D"), good);
        out.println("d.good=" + szTry(rl::getDistances));

        // empty array
        rld.setItem(COSName.getPDFName("D"), new COSArray());
        out.println("d.empty=" + szTry(rl::getDistances));

        // array with non-dict members mixed in (int, string, dict)
        COSArray mixed = new COSArray();
        mixed.add(COSInteger.get(3));
        mixed.add(nfDict("ft"));
        mixed.add(new COSString("x"));
        rld.setItem(COSName.getPDFName("D"), mixed);
        out.println("d.mixed=" + szTry(rl::getDistances));

        // bare dictionary (non-array) at /D
        rld.setItem(COSName.getPDFName("D"), nfDict("yd"));
        out.println("d.dict=" + szTry(rl::getDistances));

        // integer (non-array) at /D
        rld.setItem(COSName.getPDFName("D"), COSInteger.get(5));
        out.println("d.int=" + szTry(rl::getDistances));

        // remove -> absent
        rld.removeItem(COSName.getPDFName("D"));
        out.println("d.absent=" + szTry(rl::getDistances));

        // ---- /X /Y /A /T /S quick shape pass -------------------------------
        rld.setItem(COSName.getPDFName("X"), new COSArray());
        out.println("x.empty=" + szTry(rl::getChangeXs));
        rld.setItem(COSName.getPDFName("Y"), nfDict("a"));
        out.println("y.dict=" + szTry(rl::getChangeYs));
        rld.setItem(COSName.getPDFName("A"), COSInteger.get(1));
        out.println("a.int=" + szTry(rl::getAreas));
        rld.setItem(COSName.getPDFName("T"), good);
        out.println("t.good=" + szTry(rl::getAngles));
        out.println("s.absent=" + szTry(rl::getLineSloaps));

        // ---- /R scale ratio shapes -----------------------------------------
        PDRectlinearMeasureDictionary r2 = new PDRectlinearMeasureDictionary();
        r2.getCOSObject().setItem(COSName.R, new COSString("1in = 1mi"));
        out.println("r.string=" + nz(r2.getScaleRatio()));
        r2.getCOSObject().setName(COSName.R, "ratio");
        out.println("r.name=" + nz(r2.getScaleRatio()));
        r2.getCOSObject().setItem(COSName.R, COSInteger.get(2));
        out.println("r.int=" + nz(r2.getScaleRatio()));

        // ---- /O coord origin shapes ----------------------------------------
        PDRectlinearMeasureDictionary r3 = new PDRectlinearMeasureDictionary();
        COSArray o4 = new COSArray();
        o4.add(new COSFloat(1.5f));
        o4.add(COSInteger.get(2));
        r3.getCOSObject().setItem(COSName.getPDFName("O"), o4);
        out.println("o.floatarr=" + farr(r3.getCoordSystemOrigin()));
        r3.getCOSObject().setItem(COSName.getPDFName("O"), COSInteger.get(9));
        out.println("o.int=" + farr(r3.getCoordSystemOrigin()));
        r3.getCOSObject().removeItem(COSName.getPDFName("O"));
        out.println("o.absent=" + farr(r3.getCoordSystemOrigin()));

        // ---- /CYX shapes ---------------------------------------------------
        PDRectlinearMeasureDictionary r4 = new PDRectlinearMeasureDictionary();
        r4.getCOSObject().setItem(COSName.getPDFName("CYX"), COSInteger.get(3));
        out.println("cyx.int=" + r4.getCYX());
        r4.getCOSObject().setItem(COSName.getPDFName("CYX"), new COSFloat(0.5f));
        out.println("cyx.float=" + r4.getCYX());
        r4.getCOSObject().setItem(COSName.getPDFName("CYX"), new COSString("nan"));
        out.println("cyx.string=" + r4.getCYX());
        r4.getCOSObject().removeItem(COSName.getPDFName("CYX"));
        out.println("cyx.absent=" + r4.getCYX());

        // ---- number format /C conversion edge values -----------------------
        PDNumberFormatDictionary nf = new PDNumberFormatDictionary();
        nf.setConversionFactor(-2.5f);
        out.println("c.negative=" + nf.getConversionFactor());
        nf.setConversionFactor(0f);
        out.println("c.zero=" + nf.getConversionFactor());
        nf.getCOSObject().setItem(COSName.C, new COSString("notnum"));
        out.println("c.string=" + nf.getConversionFactor());
        nf.getCOSObject().removeItem(COSName.C);
        out.println("c.absent=" + nf.getConversionFactor());

        // ---- number format /D precision shapes -----------------------------
        PDNumberFormatDictionary nf2 = new PDNumberFormatDictionary();
        nf2.getCOSObject().setItem(COSName.D, COSInteger.get(16));
        out.println("nfd.int=" + nf2.getDenominator());
        nf2.getCOSObject().setItem(COSName.D, new COSFloat(4.7f));
        out.println("nfd.float=" + nf2.getDenominator());
        nf2.getCOSObject().setItem(COSName.D, new COSString("z"));
        out.println("nfd.string=" + nf2.getDenominator());
        nf2.getCOSObject().removeItem(COSName.D);
        out.println("nfd.absent=" + nf2.getDenominator());

        // ---- number format /F format style shapes --------------------------
        PDNumberFormatDictionary nf3 = new PDNumberFormatDictionary();
        // valid set via setter
        nf3.setFractionalDisplay("R");
        out.println("f.valid=" + nz(nf3.getFractionalDisplay()));
        // unknown name written straight to COS (bypass setter validation)
        nf3.getCOSObject().setName(COSName.F, "Q");
        out.println("f.unknown_name=" + nz(nf3.getFractionalDisplay()));
        // as COSString "F"
        nf3.getCOSObject().setItem(COSName.F, new COSString("F"));
        out.println("f.string=" + nz(nf3.getFractionalDisplay()));
        nf3.getCOSObject().removeItem(COSName.F);
        out.println("f.absent=" + nz(nf3.getFractionalDisplay()));
        // setter rejecting unknown
        String fErr;
        try {
            nf3.setFractionalDisplay("Q");
            fErr = "NO_THROW";
        } catch (RuntimeException e) {
            fErr = e.getClass().getSimpleName();
        }
        out.println("f.setter_bad=" + fErr);

        // ---- number format /U units shapes ---------------------------------
        PDNumberFormatDictionary nf4 = new PDNumberFormatDictionary();
        nf4.getCOSObject().setString(COSName.getPDFName("U"), "metres");
        out.println("u.string=" + nz(nf4.getUnits()));
        nf4.getCOSObject().setName(COSName.getPDFName("U"), "metres");
        out.println("u.name=" + nz(nf4.getUnits()));
        nf4.getCOSObject().setItem(COSName.getPDFName("U"), COSInteger.get(1));
        out.println("u.int=" + nz(nf4.getUnits()));

        // ---- number format /O label position setter validation -------------
        PDNumberFormatDictionary nf5 = new PDNumberFormatDictionary();
        String oErr;
        try {
            nf5.setLabelPositionToValue("Z");
            oErr = "NO_THROW";
        } catch (RuntimeException e) {
            oErr = e.getClass().getSimpleName();
        }
        out.println("o.setter_bad=" + oErr);
        // unknown name straight to COS -> getter returns raw, no default
        nf5.getCOSObject().setName(COSName.getPDFName("O"), "Z");
        out.println("o.unknown_name=" + nz(nf5.getLabelPositionToValue()));

        // ---- viewport /BBox arity ------------------------------------------
        PDViewportDictionary v = new PDViewportDictionary();
        v.getCOSObject().setItem(COSName.BBOX, new COSArray());
        out.println("bbox.empty=" + (v.getBBox() == null ? "NULL" : "present"));
        COSArray two = new COSArray();
        two.add(COSInteger.get(0));
        two.add(COSInteger.get(0));
        v.getCOSObject().setItem(COSName.BBOX, two);
        String bbox2;
        try {
            bbox2 = v.getBBox() == null ? "NULL" : "w:" + v.getBBox().getWidth();
        } catch (RuntimeException e) {
            bbox2 = e.getClass().getSimpleName();
        }
        out.println("bbox.two=" + bbox2);
        v.setBBox(new PDRectangle(0, 0, 100, 200));
        out.println("bbox.four=w:" + v.getBBox().getWidth());

        // ---- viewport /Name shapes -----------------------------------------
        PDViewportDictionary v2 = new PDViewportDictionary();
        v2.getCOSObject().setName(COSName.getPDFName("Name"), "Imperial");
        out.println("name.name=" + nz(v2.getName()));
        v2.getCOSObject().setItem(COSName.getPDFName("Name"), new COSString("Metric"));
        out.println("name.string=" + nz(v2.getName()));
        v2.getCOSObject().setItem(COSName.getPDFName("Name"), COSInteger.get(4));
        out.println("name.int=" + nz(v2.getName()));

        // ---- viewport /Measure dispatch ------------------------------------
        PDViewportDictionary v3 = new PDViewportDictionary();
        // non-dict measure
        v3.getCOSObject().setItem(COSName.MEASURE, COSInteger.get(1));
        out.println("measure.int=" + (v3.getMeasure() == null ? "NULL" : "present"));
        // RL-subtype dict -> base or subclass?
        COSDictionary md = new COSDictionary();
        md.setName(COSName.SUBTYPE, "RL");
        v3.getCOSObject().setItem(COSName.MEASURE, md);
        PDMeasureDictionary got = v3.getMeasure();
        out.println("measure.rl.class=" + (got == null ? "NULL" : got.getClass().getSimpleName()));
        out.println("measure.rl.subtype=" + (got == null ? "NULL" : got.getSubtype()));
        out.println("measure.absent=" + (new PDViewportDictionary().getMeasure() == null ? "NULL" : "present"));
    }
}
