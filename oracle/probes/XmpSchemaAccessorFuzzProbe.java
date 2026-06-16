import java.io.PrintStream;
import java.util.Calendar;
import java.util.GregorianCalendar;
import java.util.List;
import java.util.TimeZone;
import org.apache.xmpbox.XMPMetadata;
import org.apache.xmpbox.schema.AdobePDFSchema;
import org.apache.xmpbox.schema.DublinCoreSchema;
import org.apache.xmpbox.schema.XMPBasicSchema;
import org.apache.xmpbox.schema.XMPRightsManagementSchema;
import org.apache.xmpbox.type.TextType;

/**
 * Live oracle probe for the xmpbox SCHEMA-SPECIFIC TYPED ACCESSORS.
 *
 * Unlike the parse-a-packet probes (XmpSchemaProbe / XmpDublinCoreProbe), this
 * probe builds an {@link XMPMetadata} + its schemas PROGRAMMATICALLY and drives
 * the typed getters / setters with cardinality (text / bag / seq / lang-alt),
 * mirroring how a pypdfbox caller would use them in code. Each case is selected
 * by its id (first arg) so the Python side runs one probe invocation per case
 * and compares the projected result line-for-line.
 *
 * Usage: java -cp <xmpbox.jar>:<build> XmpSchemaAccessorFuzzProbe <case-id>
 *
 * Output (UTF-8, stdout): one or more "key = value" lines, or "ERROR
 * <ClassSimpleName>" when the operation throws. A getter that returns Java null
 * emits "key = __NULL__". Multi-valued lists join with the US (0x1f) separator.
 * Calendars render via the canonical epochMillis@offsetMinutes form so Java's
 * Calendar and pypdfbox's datetime compare repr-independently.
 */
public final class XmpSchemaAccessorFuzzProbe {
    private static final char US = (char) 0x1f;
    private static final String NULL = "__NULL__";

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String id = args[0];
        try {
            run(out, id);
        } catch (Throwable t) {
            out.print("ERROR " + t.getClass().getSimpleName() + "\n");
        }
    }

    private static void run(PrintStream out, String id) throws Exception {
        XMPMetadata meta = XMPMetadata.createXMPMetadata();
        switch (id) {
            // ---- Dublin Core: title (LangAlt) -----------------------------
            case "dc_title_default": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.setTitle("Hello");
                emit(out, "get", dc.getTitle());
                emit(out, "get_xdefault", dc.getTitle("x-default"));
                break;
            }
            case "dc_title_lang_then_get_default": {
                // Set ONLY a non-default language, then read the no-arg getter.
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.setTitle("fr", "Bonjour");
                emit(out, "get", dc.getTitle());
                emit(out, "get_fr", dc.getTitle("fr"));
                emitList(out, "langs", langList(dc, "title"));
                break;
            }
            case "dc_title_overwrite_default": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.setTitle("first");
                dc.setTitle("second");
                emit(out, "get", dc.getTitle());
                emitList(out, "langs", langList(dc, "title"));
                break;
            }
            case "dc_title_xdefault_reorder": {
                // Add fr first, then x-default; check x-default moves to front.
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.setTitle("fr", "Bonjour");
                dc.setTitle("x-default", "Hi");
                emitList(out, "langs", langList(dc, "title"));
                emit(out, "get", dc.getTitle());
                break;
            }
            case "dc_title_absent": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                emit(out, "get", dc.getTitle());
                emit(out, "prop", dc.getTitleProperty() == null ? NULL : "present");
                break;
            }
            case "dc_description_missing_default_lang": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.addDescription("de", "Beschreibung");
                emit(out, "get_default", dc.getDescription());
                emit(out, "get_de", dc.getDescription("de"));
                break;
            }

            // ---- Dublin Core: creator (Seq) -------------------------------
            case "dc_creator_order": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.addCreator("Charlie");
                dc.addCreator("Alice");
                dc.addCreator("Bob");
                emitList(out, "creators", dc.getCreators());
                break;
            }
            case "dc_creator_dup": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.addCreator("Same");
                dc.addCreator("Same");
                emitList(out, "creators", dc.getCreators());
                break;
            }
            case "dc_creator_remove": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.addCreator("A");
                dc.addCreator("B");
                dc.addCreator("C");
                dc.removeCreator("B");
                emitList(out, "creators", dc.getCreators());
                break;
            }
            case "dc_creator_remove_absent": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.addCreator("A");
                dc.removeCreator("ZZZ");
                emitList(out, "creators", dc.getCreators());
                break;
            }
            case "dc_creators_absent": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                emitList(out, "creators", dc.getCreators());
                break;
            }

            // ---- Dublin Core: subject (Bag) -------------------------------
            case "dc_subject_order": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.addSubject("z");
                dc.addSubject("a");
                dc.addSubject("m");
                emitList(out, "subjects", dc.getSubjects());
                break;
            }
            case "dc_subject_remove": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.addSubject("x");
                dc.addSubject("y");
                dc.removeSubject("x");
                emitList(out, "subjects", dc.getSubjects());
                break;
            }

            // ---- Dublin Core: date (Seq of Date) --------------------------
            case "dc_date_order": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.addDate(cal(2020, 1, 1, "UTC"));
                dc.addDate(cal(2019, 6, 15, "UTC"));
                List<Calendar> dates = dc.getDates();
                emitCalendars(out, "dates", dates);
                break;
            }
            case "dc_date_tz": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.addDate(cal(2021, 3, 1, "GMT+02:00"));
                emitCalendars(out, "dates", dc.getDates());
                break;
            }
            case "dc_dates_absent": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                List<Calendar> dates = dc.getDates();
                emitCalendars(out, "dates", dates);
                break;
            }

            // ---- Dublin Core: simple text fields --------------------------
            case "dc_format": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                dc.setFormat("application/pdf");
                emit(out, "format", dc.getFormat());
                break;
            }
            case "dc_coverage_absent": {
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                emit(out, "coverage", dc.getCoverage());
                break;
            }

            // ---- Adobe PDF schema -----------------------------------------
            case "pdf_producer": {
                AdobePDFSchema ap = meta.createAndAddAdobePDFSchema();
                ap.setProducer("pypdfbox");
                emit(out, "producer", ap.getProducer());
                break;
            }
            case "pdf_producer_absent": {
                AdobePDFSchema ap = meta.createAndAddAdobePDFSchema();
                emit(out, "producer", ap.getProducer());
                break;
            }
            case "pdf_keywords": {
                AdobePDFSchema ap = meta.createAndAddAdobePDFSchema();
                ap.setKeywords("a, b, c");
                emit(out, "keywords", ap.getKeywords());
                break;
            }
            case "pdf_version_absent": {
                AdobePDFSchema ap = meta.createAndAddAdobePDFSchema();
                emit(out, "version", ap.getPDFVersion());
                break;
            }
            case "pdf_version_set": {
                AdobePDFSchema ap = meta.createAndAddAdobePDFSchema();
                ap.setPDFVersion("1.7");
                emit(out, "version", ap.getPDFVersion());
                break;
            }
            case "pdf_version_overwrite": {
                AdobePDFSchema ap = meta.createAndAddAdobePDFSchema();
                ap.setPDFVersion("1.4");
                ap.setPDFVersion("2.0");
                emit(out, "version", ap.getPDFVersion());
                break;
            }
            case "pdf_producer_empty": {
                AdobePDFSchema ap = meta.createAndAddAdobePDFSchema();
                ap.setProducer("");
                emit(out, "producer", ap.getProducer());
                break;
            }

            // ---- XMP Basic schema -----------------------------------------
            case "xb_creatortool_absent": {
                XMPBasicSchema xb = meta.createAndAddXMPBasicSchema();
                emit(out, "tool", xb.getCreatorTool());
                break;
            }
            case "xb_creatortool": {
                XMPBasicSchema xb = meta.createAndAddXMPBasicSchema();
                xb.setCreatorTool("Tool 1.0");
                emit(out, "tool", xb.getCreatorTool());
                break;
            }
            case "xb_createdate": {
                XMPBasicSchema xb = meta.createAndAddXMPBasicSchema();
                xb.setCreateDate(cal(2022, 12, 25, "UTC"));
                emitCalendar(out, "create", xb.getCreateDate());
                break;
            }
            case "xb_createdate_tz": {
                XMPBasicSchema xb = meta.createAndAddXMPBasicSchema();
                xb.setCreateDate(cal(2022, 12, 25, "GMT-05:00"));
                emitCalendar(out, "create", xb.getCreateDate());
                break;
            }
            case "xb_createdate_absent": {
                XMPBasicSchema xb = meta.createAndAddXMPBasicSchema();
                emitCalendar(out, "create", xb.getCreateDate());
                break;
            }
            case "xb_modifydate": {
                XMPBasicSchema xb = meta.createAndAddXMPBasicSchema();
                xb.setModifyDate(cal(2023, 1, 2, "UTC"));
                emitCalendar(out, "modify", xb.getModifyDate());
                break;
            }
            case "xb_metadatadate_absent": {
                XMPBasicSchema xb = meta.createAndAddXMPBasicSchema();
                emitCalendar(out, "meta", xb.getMetadataDate());
                break;
            }
            case "xb_label": {
                XMPBasicSchema xb = meta.createAndAddXMPBasicSchema();
                xb.setLabel("Red");
                emit(out, "label", xb.getLabel());
                break;
            }
            case "xb_rating": {
                XMPBasicSchema xb = meta.createAndAddXMPBasicSchema();
                xb.setRating(4);
                emitInt(out, "rating", xb.getRating());
                break;
            }
            case "xb_rating_absent": {
                XMPBasicSchema xb = meta.createAndAddXMPBasicSchema();
                emitInt(out, "rating", xb.getRating());
                break;
            }
            case "xb_rating_negative": {
                XMPBasicSchema xb = meta.createAndAddXMPBasicSchema();
                xb.setRating(-5);
                emitInt(out, "rating", xb.getRating());
                break;
            }
            case "xb_identifier_bag": {
                XMPBasicSchema xb = meta.createAndAddXMPBasicSchema();
                xb.addIdentifier("id-2");
                xb.addIdentifier("id-1");
                emitList(out, "ids", xb.getIdentifiers());
                break;
            }

            // ---- XMP Rights Management schema -----------------------------
            case "rights_marked_true": {
                XMPRightsManagementSchema r = meta.createAndAddXMPRightsManagementSchema();
                r.setMarked(true);
                emitBool(out, "marked", r.getMarked());
                break;
            }
            case "rights_marked_false": {
                XMPRightsManagementSchema r = meta.createAndAddXMPRightsManagementSchema();
                r.setMarked(false);
                emitBool(out, "marked", r.getMarked());
                break;
            }
            case "rights_marked_absent": {
                XMPRightsManagementSchema r = meta.createAndAddXMPRightsManagementSchema();
                emitBool(out, "marked", r.getMarked());
                break;
            }
            case "rights_owner_bag": {
                XMPRightsManagementSchema r = meta.createAndAddXMPRightsManagementSchema();
                r.addOwner("Owner B");
                r.addOwner("Owner A");
                emitList(out, "owners", r.getOwners());
                break;
            }
            case "rights_owner_remove": {
                XMPRightsManagementSchema r = meta.createAndAddXMPRightsManagementSchema();
                r.addOwner("X");
                r.addOwner("Y");
                r.removeOwner("X");
                emitList(out, "owners", r.getOwners());
                break;
            }
            case "rights_usageterms_lang": {
                XMPRightsManagementSchema r = meta.createAndAddXMPRightsManagementSchema();
                r.addUsageTerms("en", "Use freely");
                r.addUsageTerms("fr", "Utilisez librement");
                emit(out, "default", r.getUsageTerms());
                emit(out, "en", r.getUsageTerms("en"));
                break;
            }
            case "rights_usageterms_default": {
                XMPRightsManagementSchema r = meta.createAndAddXMPRightsManagementSchema();
                r.addUsageTerms("x-default", "Default terms");
                emit(out, "default", r.getUsageTerms());
                break;
            }
            case "rights_certificate_absent": {
                XMPRightsManagementSchema r = meta.createAndAddXMPRightsManagementSchema();
                emit(out, "cert", r.getCertificate());
                break;
            }
            case "rights_webstatement": {
                XMPRightsManagementSchema r = meta.createAndAddXMPRightsManagementSchema();
                r.setWebStatement("http://example.com/rights");
                emit(out, "web", r.getWebStatement());
                break;
            }

            // ---- cross-schema: reading from the wrong namespace -----------
            case "cross_schema_producer_on_dc": {
                // Producer lives on the pdf schema, not dc — reading dc must
                // not surface it.
                meta.createAndAddAdobePDFSchema().setProducer("ProdX");
                DublinCoreSchema dc = meta.createAndAddDublinCoreSchema();
                emit(out, "dc_format", dc.getFormat());
                emit(out, "pdf_producer", meta.getAdobePDFSchema().getProducer());
                break;
            }

            default:
                out.print("ERROR UnknownCase\n");
        }
    }

    private static List<String> langList(DublinCoreSchema dc, String prop)
            throws Exception {
        return dc.getUnqualifiedLanguagePropertyLanguagesValue(prop);
    }

    private static Calendar cal(int year, int month, int day, String tz) {
        Calendar c = new GregorianCalendar(TimeZone.getTimeZone(tz));
        c.clear();
        c.set(year, month - 1, day, 0, 0, 0);
        c.set(Calendar.MILLISECOND, 0);
        return c;
    }

    // --- emitters ----------------------------------------------------------

    private static void emit(PrintStream out, String key, String value) {
        out.print(key + " = " + (value == null ? NULL : value) + "\n");
    }

    private static void emitInt(PrintStream out, String key, Integer value) {
        out.print(key + " = " + (value == null ? NULL : value.toString()) + "\n");
    }

    private static void emitBool(PrintStream out, String key, Boolean value) {
        out.print(key + " = " + (value == null ? NULL : value.toString()) + "\n");
    }

    private static void emitList(PrintStream out, String key, List<String> values) {
        if (values == null) {
            out.print(key + " = " + NULL + "\n");
            return;
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < values.size(); i++) {
            if (i > 0) {
                sb.append(US);
            }
            sb.append(values.get(i));
        }
        out.print(key + " = " + sb + "\n");
    }

    private static void emitCalendar(PrintStream out, String key, Calendar cal) {
        out.print(key + " = " + (cal == null ? NULL : fmtCalendar(cal)) + "\n");
    }

    private static void emitCalendars(PrintStream out, String key, List<Calendar> cals) {
        if (cals == null) {
            out.print(key + " = " + NULL + "\n");
            return;
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < cals.size(); i++) {
            if (i > 0) {
                sb.append(US);
            }
            sb.append(fmtCalendar(cals.get(i)));
        }
        out.print(key + " = " + sb + "\n");
    }

    private static String fmtCalendar(Calendar cal) {
        long epochMillis = cal.getTimeInMillis();
        int offsetMinutes =
                (cal.get(Calendar.ZONE_OFFSET) + cal.get(Calendar.DST_OFFSET)) / 60000;
        return epochMillis + "@" + offsetMinutes;
    }
}
