import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { DayPicker } from "react-day-picker";

import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";

export type CalendarProps = React.ComponentProps<typeof DayPicker>;

function Calendar({ className, classNames, showOutsideDays = true, ...props }: CalendarProps) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      className={cn("p-4", className)}
      classNames={{
        months: "flex flex-col sm:flex-row space-y-4 sm:space-x-4 sm:space-y-0",
        month: "space-y-4",
        caption: "flex justify-center pt-1 relative items-center mb-4",
        caption_label: "text-lg font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent",
        nav: "space-x-1 flex items-center",
        nav_button: cn(
          buttonVariants({ variant: "outline" }),
          "h-9 w-9 bg-gradient-to-br from-slate-50 to-gray-100 dark:from-slate-800 dark:to-gray-900 border-2 p-0 hover:from-blue-50 hover:to-indigo-50 dark:hover:from-blue-950 dark:hover:to-indigo-950 hover:border-blue-300 transition-all duration-300 shadow-sm hover:shadow-md",
        ),
        nav_button_previous: "absolute left-1",
        nav_button_next: "absolute right-1",
        table: "w-full border-collapse space-y-1",
        head_row: "flex mb-2",
        head_cell: "text-muted-foreground rounded-lg w-11 font-semibold text-xs uppercase tracking-wider bg-gradient-to-br from-slate-100 to-gray-200 dark:from-slate-800 dark:to-gray-900 py-2 shadow-sm",
        row: "flex w-full mt-2",
        cell: "h-11 w-11 text-center text-sm p-0 relative [&:has([aria-selected].day-range-end)]:rounded-r-md [&:has([aria-selected].day-outside)]:bg-accent/50 [&:has([aria-selected])]:bg-accent first:[&:has([aria-selected])]:rounded-l-md last:[&:has([aria-selected])]:rounded-r-md focus-within:relative focus-within:z-20",
        day: cn(
          buttonVariants({ variant: "ghost" }),
          "h-11 w-11 p-0 font-semibold aria-selected:opacity-100 rounded-xl transition-all duration-300 hover:scale-110 hover:shadow-lg relative overflow-hidden",
          "before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/20 before:to-transparent before:opacity-0 hover:before:opacity-100 before:transition-opacity before:duration-300"
        ),
        day_range_end: "day-range-end",
        day_selected:
          "bg-gradient-to-br from-blue-500 to-indigo-600 text-white font-bold hover:from-blue-600 hover:to-indigo-700 focus:from-blue-600 focus:to-indigo-700 shadow-lg hover:shadow-xl scale-105",
        day_today: "bg-gradient-to-br from-emerald-400 to-teal-500 text-white font-bold shadow-md ring-2 ring-emerald-300 ring-offset-2 dark:ring-offset-gray-950",
        day_outside:
          "day-outside text-muted-foreground opacity-40 aria-selected:bg-accent/50 aria-selected:text-muted-foreground aria-selected:opacity-30",
        day_disabled: "text-muted-foreground opacity-30 line-through",
        day_range_middle: "aria-selected:bg-gradient-to-r aria-selected:from-blue-100 aria-selected:to-indigo-100 dark:aria-selected:from-blue-950 dark:aria-selected:to-indigo-950 aria-selected:text-accent-foreground",
        day_hidden: "invisible",
        ...classNames,
      }}
      components={{
        IconLeft: ({ ..._props }) => <ChevronLeft className="h-5 w-5" />,
        IconRight: ({ ..._props }) => <ChevronRight className="h-5 w-5" />,
      }}
      {...props}
    />
  );
}
Calendar.displayName = "Calendar";

export { Calendar };
