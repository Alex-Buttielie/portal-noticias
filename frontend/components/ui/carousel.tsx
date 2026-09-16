"use client";

import * as React from "react";
import useEmblaCarousel from "embla-carousel-react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

type EmblaApi = ReturnType<typeof useEmblaCarousel>[1];

interface CarouselProps extends React.HTMLAttributes<HTMLDivElement> {
  opts?: Parameters<typeof useEmblaCarousel>[0];
  plugins?: Parameters<typeof useEmblaCarousel>[1];
  orientation?: "horizontal" | "vertical";
  setApi?: (api: NonNullable<EmblaApi>) => void;
}

const Carousel = React.forwardRef<HTMLDivElement, CarouselProps>(
  ({ className, opts, plugins, orientation = "horizontal", setApi, children, ...props }, ref) => {
    const [scrollSnaps, setScrollSnaps] = React.useState<number[]>([]);
    const [selectedIndex, setSelectedIndex] = React.useState(0);
    const [scrollProgress, setScrollProgress] = React.useState(0);
    const [api, setApiInternal] = React.useState<NonNullable<EmblaApi> | null>(null);
    const containerRef = React.useRef<HTMLDivElement>(null);

    const handleInit = React.useCallback((emblaApi: NonNullable<EmblaApi>) => {
      setApiInternal(emblaApi);
      setScrollSnaps(emblaApi.scrollSnapList());
      setSelectedIndex(emblaApi.selectedScrollSnap());
      setScrollProgress(emblaApi.scrollProgress());
      setApi?.(emblaApi);
    }, [setApi]);

    React.useEffect(() => {
      if (!api) return;

      const onSelect = () => setSelectedIndex(api.selectedScrollSnap());
      const onScroll = () => {
        setScrollProgress(api.scrollProgress());
      };

      api.on("select", onSelect);
      api.on("scroll", onScroll);
      api.on("init", handleInit);
      api.on("reInit", handleInit);

      return () => {
        api.off("select", onSelect);
        api.off("scroll", onScroll);
        api.off("init", handleInit);
        api.off("reInit", handleInit);
      };
    }, [api, handleInit]);

    const scrollPrev = React.useCallback(() => {
      api?.scrollPrev();
    }, [api]);

    const scrollNext = React.useCallback(() => {
      api?.scrollNext();
    }, [api]);

    const [emblaRef, emblaApi] = useEmblaCarousel(opts, plugins);
    
    React.useEffect(() => {
      if (emblaApi) handleInit(emblaApi);
    }, [emblaApi, handleInit]);

    React.useEffect(() => {
      if (containerRef.current && emblaRef) {
        (emblaRef as (el: HTMLDivElement | null) => void)(containerRef.current);
      }
    }, [emblaRef]);

    React.useImperativeHandle(ref, () => containerRef.current!, []);

    return (
      <div
        ref={containerRef}
        className={cn("relative", className)}
        {...props}
      >
        <div className="overflow-hidden">
          <div
            className={cn(
              "flex",
              orientation === "horizontal" ? "flex-row" : "flex-col"
            )}
          >
            {React.Children.map(children, (child) =>
              React.isValidElement<{ className?: string }>(child)
                ? React.cloneElement(child, {
                    className: cn("flex-[0_0_100%]", child.props.className),
                  })
                : child
            )}
          </div>
        </div>
        <CarouselControls
          api={api}
          scrollPrev={scrollPrev}
          scrollNext={scrollNext}
          selectedIndex={selectedIndex}
          scrollSnaps={scrollSnaps}
          orientation={orientation}
        />
      </div>
    );
  }
);
Carousel.displayName = "Carousel";

const CarouselControls = ({
  api,
  scrollPrev,
  scrollNext,
  selectedIndex,
  scrollSnaps,
  orientation,
}: {
  api: NonNullable<EmblaApi> | null;
  scrollPrev: () => void;
  scrollNext: () => void;
  selectedIndex: number;
  scrollSnaps: number[];
  orientation: "horizontal" | "vertical";
}) => {
  const isHorizontal = orientation === "horizontal";

  return (
    <div className="flex items-center justify-center gap-2 pt-4">
      <button
        type="button"
        onClick={scrollPrev}
        disabled={!api || selectedIndex === 0}
        className={cn(
          "inline-flex items-center justify-center rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-2 text-[var(--cor-texto)] transition-colors",
          "hover:bg-[var(--cor-borda)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
          "disabled:pointer-events-none disabled:opacity-50",
          "motion-reduce:transition-none touch-manipulation min-h-[44px] min-w-[44px]",
          isHorizontal && "rotate-0",
          !isHorizontal && "rotate-90"
        )}
        aria-label="Anterior"
      >
        <ChevronLeft className="h-5 w-5" aria-hidden="true" />
      </button>
      <div className="flex items-center gap-1" role="tablist" aria-label="Slides do carrossel">
        {scrollSnaps.map((_, index) => (
          <button
            key={index}
            type="button"
            onClick={() => api?.scrollTo(index)}
            className={cn(
              "flex min-h-[44px] min-w-[44px] touch-manipulation items-center justify-center rounded-full",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
              "motion-reduce:transition-none"
            )}
            aria-label={`Ir para slide ${index + 1}`}
            aria-current={index === selectedIndex ? "true" : undefined}
          >
            <span
              aria-hidden="true"
              className={cn(
                "h-2 w-2 rounded-full transition-colors motion-reduce:transition-none",
                index === selectedIndex
                  ? "bg-[var(--cor-primaria)]"
                  : "bg-[var(--cor-texto-suave)]/50 hover:bg-[var(--cor-texto-suave)]"
              )}
            />
          </button>
        ))}
      </div>
      <button
        type="button"
        onClick={scrollNext}
        disabled={!api || selectedIndex === scrollSnaps.length - 1}
        className={cn(
          "inline-flex items-center justify-center rounded-full border border-[var(--cor-borda)] bg-[var(--cor-fundo)] p-2 text-[var(--cor-texto)] transition-colors",
          "hover:bg-[var(--cor-borda)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
          "disabled:pointer-events-none disabled:opacity-50",
          "motion-reduce:transition-none touch-manipulation min-h-[44px] min-w-[44px]",
          isHorizontal && "rotate-0",
          !isHorizontal && "rotate-90"
        )}
        aria-label="Próximo"
      >
        <ChevronRight className="h-5 w-5" aria-hidden="true" />
      </button>
    </div>
  );
};

export { Carousel, type EmblaApi };