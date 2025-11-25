import * as React from "react";
import { Calendar } from "@/components/ui/calendar";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DayPicker } from "react-day-picker";

type CalendarWithSelectProps = React.ComponentProps<typeof DayPicker> & {
  currentMonth?: Date;
  onMonthChange?: (date: Date) => void;
};

export function CalendarWithSelect({
  currentMonth = new Date(),
  onMonthChange,
  ...props
}: CalendarWithSelectProps) {
  const [month, setMonth] = React.useState<Date>(currentMonth);

  React.useEffect(() => {
    setMonth(currentMonth);
  }, [currentMonth]);

  const handleMonthChange = (newMonth: Date) => {
    setMonth(newMonth);
    onMonthChange?.(newMonth);
  };

  const currentYear = month.getFullYear();
  const currentMonthIndex = month.getMonth();

  const years = React.useMemo(() => {
    const currentYear = new Date().getFullYear();
    const startYear = currentYear - 10;
    const endYear = currentYear + 10;
    return Array.from({ length: endYear - startYear + 1 }, (_, i) => startYear + i);
  }, []);

  const months = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];

  const handleYearChange = (year: string) => {
    const newDate = new Date(parseInt(year), currentMonthIndex, 1);
    handleMonthChange(newDate);
  };

  const handleMonthSelect = (monthIndex: string) => {
    const newDate = new Date(currentYear, parseInt(monthIndex), 1);
    handleMonthChange(newDate);
  };

  const goToPreviousMonth = () => {
    const newDate = new Date(currentYear, currentMonthIndex - 1, 1);
    handleMonthChange(newDate);
  };

  const goToNextMonth = () => {
    const newDate = new Date(currentYear, currentMonthIndex + 1, 1);
    handleMonthChange(newDate);
  };

  return (
    <div className="space-y-4">
      {/* Month and Year Selectors */}
      <div className="flex items-center justify-between gap-2 px-4">
        <Button
          variant="outline"
          size="icon"
          onClick={goToPreviousMonth}
          className="h-9 w-9 bg-gradient-to-br from-slate-50 to-gray-100 dark:from-slate-800 dark:to-gray-900 border-2 hover:from-blue-50 hover:to-indigo-50 dark:hover:from-blue-950 dark:hover:to-indigo-950 hover:border-blue-300 transition-all duration-300 shadow-sm hover:shadow-md"
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>

        <div className="flex items-center gap-2 flex-1 justify-center">
          <Select value={currentMonthIndex.toString()} onValueChange={handleMonthSelect}>
            <SelectTrigger className="w-[140px] h-9 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950 border-2 border-blue-200 dark:border-blue-800 font-semibold">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {months.map((monthName, index) => (
                <SelectItem key={index} value={index.toString()}>
                  {monthName}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={currentYear.toString()} onValueChange={handleYearChange}>
            <SelectTrigger className="w-[100px] h-9 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950 border-2 border-blue-200 dark:border-blue-800 font-semibold">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="max-h-[300px]">
              {years.map((year) => (
                <SelectItem key={year} value={year.toString()}>
                  {year}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Button
          variant="outline"
          size="icon"
          onClick={goToNextMonth}
          className="h-9 w-9 bg-gradient-to-br from-slate-50 to-gray-100 dark:from-slate-800 dark:to-gray-900 border-2 hover:from-blue-50 hover:to-indigo-50 dark:hover:from-blue-950 dark:hover:to-indigo-950 hover:border-blue-300 transition-all duration-300 shadow-sm hover:shadow-md"
        >
          <ChevronRight className="h-5 w-5" />
        </Button>
      </div>

      {/* Calendar */}
      <Calendar
        month={month}
        onMonthChange={handleMonthChange}
        {...props}
      />
    </div>
  );
}
