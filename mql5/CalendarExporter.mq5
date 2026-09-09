//+------------------------------------------------------------------+
//|                                              CalendarExporter.mq5 |
//|                                                  ai-forex-trader  |
//+------------------------------------------------------------------+
//| Exports the MT5 terminal's built-in economic calendar to CSV so   |
//| the Python side can read it.                                      |
//|                                                                   |
//| Why this exists: MT5 ships a full economic calendar, but the      |
//| Python `MetaTrader5` package does not expose any of the           |
//| Calendar* functions — they are MQL5-only. This EA bridges the     |
//| gap by writing the calendar to a CSV that CsvCalendarSource       |
//| (mcp/calendar_source.py) reads.                                   |
//|                                                                   |
//| Read-only: this EA never places, modifies, or closes an order.    |
//| It only reads calendar data and writes a file.                    |
//|                                                                   |
//| Install: copy to MQL5\Experts\, compile in MetaEditor (F7),       |
//| attach to any chart. Output lands in MQL5\Files\.                 |
//| See docs/CALENDAR.md for the full walkthrough.                    |
//+------------------------------------------------------------------+
#property copyright "ai-forex-trader"
#property version   "1.00"
#property description "Exports the built-in MT5 economic calendar to CSV for the Python MCP server. Read-only, never trades."
#property strict

input int    DaysBack        = 7;              // History window (days back)
input int    DaysForward     = 14;             // Lookahead window (days forward)
input int    RefreshSeconds  = 300;            // Re-export interval (seconds)
input string OutputFileName  = "calendar.csv"; // Written to MQL5\Files\
input string CurrencyFilter  = "";             // e.g. "USD,EUR,GBP" — empty = all

// Written alongside the main CSV. Lets the Python side (and you) verify the
// timezone assumption documented below, which is the one thing most likely
// to be wrong on a new broker.
string MetaFileName() { return "calendar_meta.csv"; }

//+------------------------------------------------------------------+
//| Timezone handling — READ THIS BEFORE TRUSTING THE OUTPUT          |
//|                                                                   |
//| MqlCalendarValue.time is expressed in TRADE SERVER time, not UTC. |
//| Exness servers typically run GMT+2/+3 with DST, so an uncorrected |
//| timestamp can be hours off — which would make a news blackout     |
//| rule fire at the wrong time, or not at all.                       |
//|                                                                   |
//| We derive the offset from the terminal itself rather than         |
//| hardcoding it, and record it in calendar_meta.csv so the value    |
//| used is always auditable. Verify once on first run against a      |
//| known release (see docs/CALENDAR.md).                             |
//+------------------------------------------------------------------+
long ServerGmtOffsetSeconds()
{
   long raw = (long)TimeCurrent() - (long)TimeGMT();
   // Snap to the nearest 15 minutes. Server and GMT clocks drift by a few
   // seconds; without this the offset jitters between runs.
   long quarter = 900;
   long snapped = ((raw + (raw >= 0 ? quarter / 2 : -quarter / 2)) / quarter) * quarter;
   return snapped;
}

string IsoUtc(datetime t)
{
   MqlDateTime s;
   TimeToStruct(t, s);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ",
                       s.year, s.mon, s.day, s.hour, s.min, s.sec);
}

string ImportanceToString(ENUM_CALENDAR_EVENT_IMPORTANCE imp)
{
   switch(imp)
   {
      case CALENDAR_IMPORTANCE_NONE:     return "NONE";
      case CALENDAR_IMPORTANCE_LOW:      return "LOW";
      case CALENDAR_IMPORTANCE_MODERATE: return "MEDIUM";
      case CALENDAR_IMPORTANCE_HIGH:     return "HIGH";
   }
   return "NONE";
}

// Event names contain commas ("Non-Farm Employment Change, s.a.") and the
// occasional quote, so every text field is quoted and inner quotes doubled
// per RFC 4180. Without this the Python reader silently mis-columns rows.
string CsvEscape(string s)
{
   StringReplace(s, "\r", " ");
   StringReplace(s, "\n", " ");
   StringReplace(s, "\"", "\"\"");
   return "\"" + s + "\"";
}

bool CurrencyAllowed(const string currency)
{
   if(StringLen(CurrencyFilter) == 0)
      return true;
   if(StringLen(currency) == 0)
      return false;

   string wanted[];
   int n = StringSplit(CurrencyFilter, ',', wanted);
   for(int i = 0; i < n; i++)
   {
      string w = wanted[i];
      StringTrimLeft(w);
      StringTrimRight(w);
      if(StringCompare(w, currency, false) == 0)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Export                                                            |
//+------------------------------------------------------------------+
bool ExportCalendar()
{
   datetime now  = TimeCurrent();
   datetime from = now - (datetime)DaysBack * 86400;
   datetime to   = now + (datetime)DaysForward * 86400;

   MqlCalendarValue values[];
   int count = CalendarValueHistory(values, from, to, NULL, NULL);
   if(count < 0)
   {
      PrintFormat("CalendarExporter: CalendarValueHistory failed, error=%d. "
                  "Is the calendar enabled and downloaded in this terminal?",
                  GetLastError());
      return false;
   }

   long offset = ServerGmtOffsetSeconds();

   // Write to a temp file and rename into place. The Python side polls this
   // file; without the atomic swap it can read a half-written CSV and see a
   // truncated event list, which for a blackout check is worse than no data.
   string tmpName = OutputFileName + ".tmp";
   int fh = FileOpen(tmpName, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
   {
      PrintFormat("CalendarExporter: cannot open %s for writing, error=%d",
                  tmpName, GetLastError());
      return false;
   }

   FileWriteString(fh,
      "event_time_utc,currency,event_name,importance,"
      "actual,forecast,previous,revised_previous,event_id,value_id\r\n");

   int written = 0;
   for(int i = 0; i < count; i++)
   {
      MqlCalendarEvent event;
      if(!CalendarEventById(values[i].event_id, event))
         continue;

      MqlCalendarCountry country;
      if(!CalendarCountryById(event.country_id, country))
         continue;

      if(!CurrencyAllowed(country.currency))
         continue;

      datetime utc = (datetime)((long)values[i].time - offset);

      string actual   = values[i].HasActualValue()
                        ? DoubleToString(values[i].GetActualValue(), 6) : "";
      string forecast = values[i].HasForecastValue()
                        ? DoubleToString(values[i].GetForecastValue(), 6) : "";
      string previous = values[i].HasPreviousValue()
                        ? DoubleToString(values[i].GetPreviousValue(), 6) : "";
      string revised  = values[i].HasRevisedPreviousValue()
                        ? DoubleToString(values[i].GetRevisedPreviousValue(), 6) : "";

      string line = StringFormat("%s,%s,%s,%s,%s,%s,%s,%s,%I64u,%I64u\r\n",
                                 IsoUtc(utc),
                                 CsvEscape(country.currency),
                                 CsvEscape(event.name),
                                 ImportanceToString(event.importance),
                                 actual, forecast, previous, revised,
                                 values[i].event_id,
                                 values[i].id);
      FileWriteString(fh, line);
      written++;
   }
   FileClose(fh);

   if(FileIsExist(OutputFileName))
      FileDelete(OutputFileName);
   if(!FileMove(tmpName, 0, OutputFileName, FILE_REWRITE))
   {
      PrintFormat("CalendarExporter: could not move %s -> %s, error=%d",
                  tmpName, OutputFileName, GetLastError());
      return false;
   }

   WriteMeta(offset, written, from, to);
   PrintFormat("CalendarExporter: wrote %d events to %s "
               "(server->GMT offset %d s, window %s .. %s)",
               written, OutputFileName, (int)offset,
               TimeToString(from), TimeToString(to));
   return true;
}

void WriteMeta(long offset, int written, datetime from, datetime to)
{
   int fh = FileOpen(MetaFileName(), FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
      return;

   FileWriteString(fh, "key,value\r\n");
   FileWriteString(fh, StringFormat("generated_at_utc,%s\r\n", IsoUtc(TimeGMT())));
   FileWriteString(fh, StringFormat("server_time,%s\r\n", TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS)));
   FileWriteString(fh, StringFormat("gmt_time,%s\r\n", TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS)));
   FileWriteString(fh, StringFormat("server_gmt_offset_seconds,%d\r\n", (int)offset));
   FileWriteString(fh, StringFormat("event_count,%d\r\n", written));
   FileWriteString(fh, StringFormat("window_from_server,%s\r\n", TimeToString(from, TIME_DATE | TIME_SECONDS)));
   FileWriteString(fh, StringFormat("window_to_server,%s\r\n", TimeToString(to, TIME_DATE | TIME_SECONDS)));
   FileWriteString(fh, StringFormat("terminal_company,%s\r\n", TerminalInfoString(TERMINAL_COMPANY)));
   FileClose(fh);
}

//+------------------------------------------------------------------+
//| Lifecycle                                                         |
//+------------------------------------------------------------------+
int OnInit()
{
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
      Print("CalendarExporter: terminal is not connected — calendar data may be stale or empty.");

   if(RefreshSeconds < 30)
   {
      Print("CalendarExporter: RefreshSeconds below 30 is pointless — the calendar "
            "updates far more slowly than that. Clamping to 30.");
      EventSetTimer(30);
   }
   else
      EventSetTimer(RefreshSeconds);

   ExportCalendar();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   ExportCalendar();
}

// Required for an EA to compile. Deliberately empty — this EA reads the
// calendar and writes a file, and must never react to ticks by trading.
void OnTick()
{
}
//+------------------------------------------------------------------+
