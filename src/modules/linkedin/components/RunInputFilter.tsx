import { useMemo } from "react";

import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox";
import type { RunInput } from "@/lib/runs";

const ALL_INPUTS = "all";

type InputOption = {
  value: string;
  label: string;
  status: string | null;
  ordinal: number | null;
};

function inputLabel(input: RunInput): string {
  const data = input.data as { profile_url?: string };
  return data.profile_url || `Input #${input.ordinal + 1}`;
}

export function RunInputFilter({
  inputs,
  selectedInputId,
  onChange,
  className,
}: {
  inputs: RunInput[];
  selectedInputId: string | null;
  onChange: (inputId: string | null) => void;
  className?: string;
}) {
  const inputOptions = useMemo<InputOption[]>(
    () => [
      { value: ALL_INPUTS, label: "All inputs", status: null, ordinal: null },
      ...inputs.map((input) => ({
        value: input.id,
        label: inputLabel(input),
        status: input.status,
        ordinal: input.ordinal + 1,
      })),
    ],
    [inputs],
  );

  const selectedOption =
    inputOptions.find(
      (option) => option.value === (selectedInputId ?? ALL_INPUTS),
    ) ?? inputOptions[0];

  return (
    <Combobox
      items={inputOptions}
      value={selectedOption}
      onValueChange={(option) =>
        onChange(option && option.value !== ALL_INPUTS ? option.value : null)
      }
      isItemEqualToValue={(a, b) => a.value === b.value}
      itemToStringLabel={(option) => option.label}
    >
      <div className={className}>
        <ComboboxInput placeholder="Filter by profile…" />
      </div>
      <ComboboxContent>
        <ComboboxEmpty>No matching inputs.</ComboboxEmpty>
        <ComboboxList>
          {(option: InputOption) => (
            <ComboboxItem key={option.value} value={option}>
              <span className="flex min-w-0 flex-1 items-center gap-2">
                {option.ordinal != null && (
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {option.ordinal}
                  </span>
                )}
                <span className="truncate">{option.label}</span>
              </span>
              {option.status && (
                <span className="shrink-0 text-xs capitalize text-muted-foreground">
                  {option.status}
                </span>
              )}
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
