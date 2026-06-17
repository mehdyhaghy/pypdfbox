import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDMarkedContentReference;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDObjectReference;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureElement;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureNode;

/**
 * Differential malformed marked-content-reference / object-reference probe
 * (wave 1557).
 *
 * Targets the structure-element /K kid REFERENCE types — PDMarkedContentReference
 * (/Type /MCR) and PDObjectReference (/Type /OBJR) — and the polymorphic kid
 * resolution that PDStructureNode.getKids() performs (bare-int MCID vs MCR vs
 * OBJR vs child PDStructureElement). Wave 1540 already fuzzed the broad
 * PDStructureElement accessor surface and 1545 the tree root; this probe drills
 * the reference-kid accessors:
 *
 *   - MCR: getMCID (/MCID present/missing/non-int/float/negative), getPage (/Pg
 *     valid/dangling/non-dict), getStm (/Stm), toString.
 *   - OBJR: getReferencedObject (/Obj present/missing/non-ref/annot/xobject),
 *     getPage (/Pg).
 *   - getKids() kid kinds + ordering for single vs array vs mixed /K, and for
 *     MCR/OBJR dicts carrying the WRONG /Type (StructElem fallback) or no /Type.
 *
 * Two emit shapes:
 *   MCR  <name> mcid=<n> page=<page|null> stm=<stm|null> str=<toString>
 *   OBJR <name> ref=<classOrNull|ERR:..> page=<page|null>
 *   KIDS <name> kids=<kind,kind,...>
 *
 * kind grammar (matches StructElemDetailProbe): "mcid<n>" Integer MCID,
 * "elem" PDStructureElement, "mcr<mcid>" PDMarkedContentReference, "objr"
 * PDObjectReference, "node" other PDStructureNode, "null"/"other" otherwise.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> MarkedContentReferenceFuzzProbe
 */
public final class MarkedContentReferenceFuzzProbe {

    private static COSArray array(COSBase... values) {
        COSArray out = new COSArray();
        for (COSBase value : values) out.add(value);
        return out;
    }

    private static COSDictionary typed(String type) {
        COSDictionary out = new COSDictionary();
        if (type != null) out.setName(COSName.TYPE, type);
        return out;
    }

    private static COSStream stream(String subtype) {
        COSStream out = new COSStream();
        if (subtype != null) out.setName(COSName.SUBTYPE, subtype);
        return out;
    }

    private static COSDictionary pageDict() {
        COSDictionary page = new COSDictionary();
        page.setName(COSName.TYPE, "Page");
        return page;
    }

    private static COSDictionary annotDict() {
        COSDictionary annot = new COSDictionary();
        annot.setName(COSName.TYPE, "Annot");
        annot.setName(COSName.SUBTYPE, "Link");
        return annot;
    }

    // ---------- MCR ----------

    private static void mcr(String name, COSDictionary d) {
        PDMarkedContentReference mcr = new PDMarkedContentReference(d);
        StringBuilder sb = new StringBuilder();
        sb.append("MCR ").append(name);
        sb.append(" mcid=").append(safeInt(() -> mcr.getMCID()));
        sb.append(" page=").append(safe(() -> mcr.getPage() == null ? "null" : "page"));
        sb.append(" str=").append(safe(() -> mcr.toString()));
        System.out.println(sb.toString());
    }

    // ---------- OBJR ----------

    private static void objr(String name, COSDictionary d) {
        PDObjectReference objr = new PDObjectReference(d);
        StringBuilder sb = new StringBuilder();
        sb.append("OBJR ").append(name);
        sb.append(" ref=").append(safe(() -> {
            Object r = objr.getReferencedObject();
            return r == null ? "null" : r.getClass().getSimpleName();
        }));
        sb.append(" page=").append(safe(() -> objr.getPage() == null ? "null" : "page"));
        System.out.println(sb.toString());
    }

    // ---------- KIDS (polymorphic resolution via PDStructureElement.getKids) ----------

    private static void kids(String name, COSBase kEntry) {
        COSDictionary d = typed("StructElem");
        if (kEntry != null) d.setItem(COSName.K, kEntry);
        PDStructureElement elem = new PDStructureElement(d);
        StringBuilder sb = new StringBuilder();
        sb.append("KIDS ").append(name).append(" kids=").append(safe(() -> kidsStr(elem)));
        System.out.println(sb.toString());
    }

    private static String kidsStr(PDStructureElement elem) {
        List<Object> kidList = elem.getKids();
        if (kidList == null || kidList.isEmpty()) return "-";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < kidList.size(); i++) {
            if (i > 0) sb.append(',');
            sb.append(kidKind(kidList.get(i)));
        }
        return sb.toString();
    }

    private static String kidKind(Object kid) {
        if (kid == null) return "null";
        if (kid instanceof Integer) return "mcid" + kid;
        if (kid instanceof PDStructureElement) return "elem";
        if (kid instanceof PDMarkedContentReference) {
            return "mcr" + ((PDMarkedContentReference) kid).getMCID();
        }
        if (kid instanceof PDObjectReference) return "objr";
        if (kid instanceof PDStructureNode) return "node";
        return "other";
    }

    private static String safe(java.util.concurrent.Callable<String> call) {
        try {
            return call.call();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    private static String safeInt(java.util.concurrent.Callable<Integer> call) {
        try {
            return String.valueOf(call.call());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    public static void main(String[] args) {
        // ============ MCR getMCID / getPage / getStm / toString ============

        // 1. canonical MCR: /Type /MCR, /MCID present.
        COSDictionary m1 = typed("MCR");
        m1.setItem(COSName.MCID, COSInteger.get(7));
        mcr("mcid_present", m1);

        // 2. /MCID missing -> getInt sentinel -1.
        mcr("mcid_missing", typed("MCR"));

        // 3. /MCID non-int (string) -> -1.
        COSDictionary m3 = typed("MCR");
        m3.setItem(COSName.MCID, new COSString("3"));
        mcr("mcid_string", m3);

        // 4. /MCID float -> int-truncated.
        COSDictionary m4 = typed("MCR");
        m4.setItem(COSName.MCID, new COSFloat(4.9f));
        mcr("mcid_float", m4);

        // 5. /MCID name -> -1.
        COSDictionary m5 = typed("MCR");
        m5.setItem(COSName.MCID, COSName.getPDFName("9"));
        mcr("mcid_name", m5);

        // 6. /MCID negative integer (stored directly, not via setMCID guard).
        COSDictionary m6 = typed("MCR");
        m6.setItem(COSName.MCID, COSInteger.get(-2));
        mcr("mcid_negative", m6);

        // 7. /MCID zero.
        COSDictionary m7 = typed("MCR");
        m7.setItem(COSName.MCID, COSInteger.get(0));
        mcr("mcid_zero", m7);

        // 8. /Pg valid page dict.
        COSDictionary m8 = typed("MCR");
        m8.setItem(COSName.MCID, COSInteger.get(1));
        m8.setItem(COSName.PG, pageDict());
        mcr("pg_valid", m8);

        // 9. /Pg non-dict (string).
        COSDictionary m9 = typed("MCR");
        m9.setItem(COSName.PG, new COSString("nope"));
        mcr("pg_string", m9);

        // 10. /Pg array (non-dict).
        COSDictionary m10 = typed("MCR");
        m10.setItem(COSName.PG, array(COSInteger.get(1)));
        mcr("pg_array", m10);

        // 11. /Pg integer.
        COSDictionary m11 = typed("MCR");
        m11.setItem(COSName.PG, COSInteger.get(5));
        mcr("pg_int", m11);

        // 12. wrong /Type on MCR dict (OBJR) but still constructed as MCR.
        COSDictionary m12 = typed("OBJR");
        m12.setItem(COSName.MCID, COSInteger.get(11));
        mcr("wrong_type_objr", m12);

        // 13. no /Type at all.
        COSDictionary m13 = new COSDictionary();
        m13.setItem(COSName.MCID, COSInteger.get(13));
        mcr("no_type", m13);

        // 14. /Stm present (content stream) + /MCID.
        COSDictionary m14 = typed("MCR");
        m14.setItem(COSName.MCID, COSInteger.get(2));
        m14.setItem(COSName.getPDFName("Stm"), stream(null));
        mcr("stm_present", m14);

        // ============ OBJR getReferencedObject / getPage ============

        // 15. /Obj missing.
        objr("obj_missing", typed("OBJR"));

        // 16. /Obj annotation dict (/Type /Annot /Subtype /Link).
        COSDictionary o16 = typed("OBJR");
        o16.setItem(COSName.getPDFName("Obj"), annotDict());
        objr("obj_annot_link", o16);

        // 17. /Obj annotation dict with /Type /Annot but NO /Subtype.
        COSDictionary o17 = typed("OBJR");
        COSDictionary annotNoSub = new COSDictionary();
        annotNoSub.setName(COSName.TYPE, "Annot");
        o17.setItem(COSName.getPDFName("Obj"), annotNoSub);
        objr("obj_annot_nosubtype", o17);

        // 18. /Obj dict with /Subtype but no /Type (bare subtype-only annot).
        COSDictionary o18 = typed("OBJR");
        COSDictionary subOnly = new COSDictionary();
        subOnly.setName(COSName.SUBTYPE, "Widget");
        o18.setItem(COSName.getPDFName("Obj"), subOnly);
        objr("obj_subtype_only", o18);

        // 19. /Obj an empty dict (no /Type, no /Subtype).
        COSDictionary o19 = typed("OBJR");
        o19.setItem(COSName.getPDFName("Obj"), new COSDictionary());
        objr("obj_empty_dict", o19);

        // 20. /Obj a Form XObject stream.
        COSDictionary o20 = typed("OBJR");
        o20.setItem(COSName.getPDFName("Obj"), stream("Form"));
        objr("obj_form_xobject", o20);

        // 21. /Obj an Image XObject stream.
        COSDictionary o21 = typed("OBJR");
        o21.setItem(COSName.getPDFName("Obj"), stream("Image"));
        objr("obj_image_xobject", o21);

        // 22. /Obj a stream with unknown subtype (/PS).
        COSDictionary o22 = typed("OBJR");
        o22.setItem(COSName.getPDFName("Obj"), stream("PS"));
        objr("obj_unknown_stream", o22);

        // 23. /Obj a non-dict (string).
        COSDictionary o23 = typed("OBJR");
        o23.setItem(COSName.getPDFName("Obj"), new COSString("nope"));
        objr("obj_string", o23);

        // 24. /Obj an integer.
        COSDictionary o24 = typed("OBJR");
        o24.setItem(COSName.getPDFName("Obj"), COSInteger.get(99));
        objr("obj_int", o24);

        // 25. /Obj annot + /Pg valid.
        COSDictionary o25 = typed("OBJR");
        o25.setItem(COSName.getPDFName("Obj"), annotDict());
        o25.setItem(COSName.PG, pageDict());
        objr("obj_annot_pg", o25);

        // 26. /Pg non-dict on OBJR.
        COSDictionary o26 = typed("OBJR");
        o26.setItem(COSName.PG, new COSString("nope"));
        objr("pg_string", o26);

        // ============ getKids() polymorphic resolution ============

        // 27. /K single bare integer MCID.
        kids("k_single_int", COSInteger.get(4));

        // 28. /K single MCR dict.
        COSDictionary kmcr = typed("MCR");
        kmcr.setItem(COSName.MCID, COSInteger.get(8));
        kids("k_single_mcr", kmcr);

        // 29. /K single OBJR dict.
        COSDictionary kobjr = typed("OBJR");
        kobjr.setItem(COSName.getPDFName("Obj"), annotDict());
        kids("k_single_objr", kobjr);

        // 30. /K single child StructElem dict.
        kids("k_single_elem", typed("StructElem"));

        // 31. /K mixed array: int, MCR, OBJR, child elem (canonical order).
        COSDictionary mixMcr = typed("MCR");
        mixMcr.setItem(COSName.MCID, COSInteger.get(6));
        COSDictionary mixObjr = typed("OBJR");
        mixObjr.setItem(COSName.getPDFName("Obj"), annotDict());
        kids("k_mixed_all", array(COSInteger.get(2), mixMcr, mixObjr, typed("StructElem")));

        // 32. /K array with MCR that has NO /MCID -> mcr-1.
        kids("k_mcr_no_mcid", array(typed("MCR")));

        // 33. /K dict with wrong /Type (Bogus) -> skipped (None) -> empty.
        kids("k_bogus_type", typed("Bogus"));

        // 34. /K MCR dict but missing /Type entirely -> treated as StructElem.
        COSDictionary kNoType = new COSDictionary();
        kNoType.setItem(COSName.MCID, COSInteger.get(3));
        kids("k_dict_no_type", kNoType);

        // 35. /K array mixing a bogus-type dict among valid kids (skipped).
        COSDictionary mid = typed("MCR");
        mid.setItem(COSName.MCID, COSInteger.get(1));
        kids("k_array_with_bogus",
                array(COSInteger.get(0), typed("Bogus"), mid, typed("OBJR")));

        // 36. /K array with a string entry (non-int, non-dict) -> skipped.
        kids("k_array_with_string",
                array(COSInteger.get(5), new COSString("x"), typed("StructElem")));

        // 37. /K a string scalar -> not int, not dict -> empty.
        kids("k_string_scalar", new COSString("nope"));

        // 38. /K an array entry that is itself an array -> skipped.
        kids("k_nested_array", array(array(COSInteger.get(1)), COSInteger.get(2)));

        // 39. /K negative bare integer MCID (no guard on read path).
        kids("k_negative_int", COSInteger.get(-5));

        // 40. /K empty array -> empty.
        kids("k_empty_array", array());
    }
}
