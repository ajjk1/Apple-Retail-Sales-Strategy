'use client';

// Three.js WebGPU 경로 오류 방지: 브라우저에 WebGPU 미지원 시 상수 폴리필
if (typeof window !== 'undefined') {
  const w = window as unknown as Window & { GPUShaderStage?: Record<string, number>; GPUBufferUsage?: Record<string, number> };
  if (!w.GPUShaderStage) w.GPUShaderStage = { VERTEX: 1, FRAGMENT: 2, COMPUTE: 4 };
  if (!w.GPUBufferUsage) w.GPUBufferUsage = { VERTEX: 0x0020, COPY_SRC: 0x0004, COPY_DST: 0x0008, MAP_READ: 0x0001, MAP_WRITE: 0x0002, STORAGE: 0x0080 };
}

import { useRef, useEffect, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import type { GlobeMethods } from 'react-globe.gl';
import { formatCityDisplay, formatCountryDisplay } from '../../lib/country';

const MAP_IMAGE = 'https://upload.wikimedia.org/wikipedia/commons/e/ea/Equirectangular-projection.jpg';
const BORDERS_IMAGE = 'https://upload.wikimedia.org/wikipedia/commons/5/51/BlankMap-Equirectangular.svg';

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Failed to load image'));
    img.src = url;
  });
}

/** 리얼 스타일: 원본 지도 색상 유지 + 국경선만 살짝 강조 (3D 글로브 텍스처용) */
function createGlobeTexture(): Promise<string> {
  return Promise.all([loadImage(MAP_IMAGE), loadImage(BORDERS_IMAGE)])
    .then(([mapImg, bordersImg]) => {
      const w = mapImg.width;
      const h = mapImg.height;
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('Canvas context not available');
      ctx.drawImage(mapImg, 0, 0);
      const bordersCanvas = document.createElement('canvas');
      bordersCanvas.width = w;
      bordersCanvas.height = h;
      const bordersCtx = bordersCanvas.getContext('2d');
      if (!bordersCtx) throw new Error('Canvas context not available');
      bordersCtx.drawImage(bordersImg, 0, 0, w, h);
      const bordersData = bordersCtx.getImageData(0, 0, w, h);
      const bd = bordersData.data;
      for (let i = 0; i < bd.length; i += 4) {
        const lum = Math.max(bd[i], bd[i + 1], bd[i + 2]);
        if (lum >= 128) {
          bd[i] = bd[i + 1] = bd[i + 2] = 0;
          bd[i + 3] = 0;
        } else {
          bd[i] = bd[i + 1] = bd[i + 2] = 0;
          bd[i + 3] = 140;
        }
      }
      bordersCtx.putImageData(bordersData, 0, 0);
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = 1;
      ctx.drawImage(bordersCanvas, 0, 0);
      return canvas.toDataURL('image/jpeg', 0.92);
    });
}

const Globe = dynamic(() => import('react-globe.gl'), { ssr: false });

interface GlobeMapProps {
  width: number;
  height: number;
  htmlElementsData: Array<{
    type: 'country' | 'store' | 'continent';
    lat: number;
    lng: number;
    [key: string]: unknown;
  }>;
  onCountryClick: (en: string) => void;
  onStoreClick: (storeId: string, city: string, isStore: boolean) => void;
  onContinentClick: (continent: string) => void;
  onGlobeClick: () => void;
  selectedCountry?: string;
  selectedStoreId?: string;
  selectedCity?: string;
  selectedContinent?: string;
}

function getPointColor(
  d: { type: string; en?: string; store_id?: string; city?: string; isStore?: boolean; continent?: string },
  selected: { country: string; storeId: string; city: string; continent: string }
): string {
  const highlight = '#10b981';
  if (d.type === 'country' && d.en === selected.country) return highlight;
  if (d.type === 'store') {
    if (d.isStore && d.store_id === selected.storeId) return highlight;
    if (!d.isStore && d.city === selected.city) return highlight;
  }
  if (d.type === 'continent' && d.continent === selected.continent) return highlight;
  if (d.type === 'country') return '#38bdf8';
  if (d.type === 'store') return '#facc15';
  if (d.type === 'continent') return '#34d399';
  return '#94a3b8';
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

/** 마커/글자 스케일: 화면 크기만 반영, 지도 줌(altitude)과 무관 */
function getMarkerLabelBaseScale(width: number, height: number) {
  return clamp(Math.min(width, height) / 520, 0.85, 2.2);
}

function getPointRadius(d: { type: string }, scale: number): number {
  const base = d.type === 'continent' ? 0.5 : d.type === 'country' ? 0.35 : 0.28;
  return base * scale;
}

function getLabelText(d: Record<string, unknown>): string {
  if (d.type === 'country') {
    const ko = d.ko as string | undefined;
    const en = d.en as string | undefined;
    return ko && en ? `${ko}(${en})` : String(ko ?? en ?? '');
  }
  if (d.type === 'store') {
    const city = d.city as string | undefined;
    const country = d.country as string | undefined;
    const cityStr = city ? formatCityDisplay(city) : String(d.store_id ?? '');
    if (country && cityStr) return `${formatCountryDisplay(country)}, ${cityStr}`;
    return cityStr;
  }
  if (d.type === 'continent') {
    const continentKo = d.continent_ko as string | undefined;
    const continent = d.continent as string | undefined;
    return continentKo && continent ? `${continentKo}(${continent})` : String(continentKo ?? continent ?? '');
  }
  return '';
}

function getLabelSize(d: Record<string, unknown>, scale: number): number {
  const type = String(d.type ?? '');
  const base = type === 'continent' ? 0.62 : type === 'country' ? 0.50 : 0.46;
  const countryScale = typeof d.scale === 'number' ? (d.scale as number) : 1;
  return base * scale * countryScale;
}

export default function GlobeMap({
  width,
  height,
  htmlElementsData,
  onCountryClick,
  onStoreClick,
  onContinentClick,
  onGlobeClick,
  selectedCountry = '',
  selectedStoreId = '',
  selectedCity = '',
  selectedContinent = '',
}: GlobeMapProps) {
  const [globeTexture, setGlobeTexture] = useState<string | null>(null);
  const [cameraAltitude, setCameraAltitude] = useState(2.2);
  const [markerLabelScale, setMarkerLabelScale] = useState(1);
  const globeRef = useRef<GlobeMethods | null>(null);

  useEffect(() => {
    createGlobeTexture()
      .then(setGlobeTexture)
      .catch(() => setGlobeTexture(MAP_IMAGE));
  }, []);

  const handlePointOrLabelClick = useCallback(
    (d: Record<string, unknown>) => {
      const type = d.type as string;
      if (type === 'country') {
        onCountryClick(String(d.en ?? ''));
        return;
      }
      if (type === 'store') {
        onStoreClick(
          String(d.store_id ?? ''),
          String(d.city ?? ''),
          Boolean(d.isStore)
        );
        return;
      }
      if (type === 'continent') {
        onContinentClick(String(d.continent ?? ''));
      }
    },
    [onCountryClick, onStoreClick, onContinentClick]
  );

  const zoomIn = useCallback(() => {
    const next = Math.max(1.2, cameraAltitude - 0.35);
    setCameraAltitude(next);
    globeRef.current?.pointOfView({ altitude: next }, 200);
  }, [cameraAltitude]);

  const zoomOut = useCallback(() => {
    const next = Math.min(4, cameraAltitude + 0.35);
    setCameraAltitude(next);
    globeRef.current?.pointOfView({ altitude: next }, 200);
  }, [cameraAltitude]);

  const zoomReset = useCallback(() => {
    setCameraAltitude(2.2);
    globeRef.current?.pointOfView({ lat: 20, lng: 0, altitude: 2.2 }, 400);
  }, []);

  const markerLabelZoomIn = useCallback(() => setMarkerLabelScale((s) => Math.min(1.8, s + 0.2)), []);
  const markerLabelZoomOut = useCallback(() => setMarkerLabelScale((s) => Math.max(0.5, s - 0.2)), []);
  const markerLabelZoomReset = useCallback(() => setMarkerLabelScale(1), []);

  const pointsData = htmlElementsData.filter((d) => d && typeof (d as { type?: string }).type !== 'undefined');
  const labelsData = pointsData.filter((d) => getLabelText(d as Record<string, unknown>).length > 0);
  const selected = {
    country: selectedCountry,
    storeId: selectedStoreId,
    city: selectedCity,
    continent: selectedContinent,
  };
  const markerLabelBaseScale = getMarkerLabelBaseScale(width, height);
  const markerLabelScaleValue = markerLabelBaseScale * markerLabelScale;

  /** 한글 지원: HTML 요소로 라벨 렌더링 (마커/글자 줌 반영) */
  const createLabelElement = useCallback(
    (d: Record<string, unknown>) => {
      const el = document.createElement('div');
      el.textContent = getLabelText(d);
      const size = getLabelSize(d, markerLabelScaleValue);
      const fontSizePx = Math.max(8, Math.min(24, Math.round(size * 22)));
      el.style.cssText = [
        'color:#ffffff',
        'font-size:' + fontSizePx + 'px',
        'font-weight:500',
        'pointer-events:auto',
        'cursor:pointer',
        'text-shadow:0 1px 3px rgba(0,0,0,0.9)',
        'white-space:nowrap',
        'font-family:system-ui,-apple-system,Segoe UI,Malgun Gothic,sans-serif',
        'transform:translateX(12px)',
      ].join(';');
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        handlePointOrLabelClick(d);
      });
      return el;
    },
    [markerLabelScaleValue, handlePointOrLabelClick]
  );

  return (
    <div
      className="relative w-full h-full overflow-hidden rounded-xl bg-[#e0e0e8]"
      style={{ width, height }}
    >
      {globeTexture && (
        <Globe
          ref={globeRef as React.MutableRefObject<GlobeMethods | null>}
          width={width}
          height={height}
          globeImageUrl={globeTexture}
          backgroundColor="rgba(0,0,0,0)"
          showAtmosphere={true}
          atmosphereColor="#a5b4fc"
          atmosphereAltitude={0.15}
          pointsData={pointsData}
          pointLat={(d: { lat: number }) => d.lat}
          pointLng={(d: { lng: number }) => d.lng}
          pointColor={(d: Record<string, unknown>) => getPointColor(d as Parameters<typeof getPointColor>[0], selected)}
          pointRadius={(d: { type: string }) => getPointRadius(d, markerLabelScaleValue)}
          pointAltitude={0.006}
          pointResolution={10}
          labelsData={[]}
          htmlElementsData={labelsData}
          htmlLat={(d: { lat: number }) => d.lat}
          htmlLng={(d: { lng: number }) => d.lng}
          htmlAltitude={0.008}
          htmlElement={(d: Record<string, unknown>) => createLabelElement(d)}
          onPointClick={(point: object) => handlePointOrLabelClick(point as Record<string, unknown>)}
          onGlobeClick={() => onGlobeClick()}
          onGlobeReady={() => {
            globeRef.current?.pointOfView({ lat: 20, lng: 0, altitude: 2.2 }, 0);
          }}
          enablePointerInteraction={true}
        />
      )}

      {/* 줌 컨트롤: 지도 줌 / 글자 줌 분리 */}
      <div className="absolute bottom-3 right-3 flex flex-col gap-3 z-20 pointer-events-auto">
        <div className="flex flex-col gap-1">
          <span className="text-[10px] font-medium text-[#6e6e73] px-1">지도</span>
          <div className="flex flex-col gap-1">
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); zoomIn(); }}
              className="w-9 h-9 flex items-center justify-center rounded-lg bg-white/95 border border-gray-200 text-[#1d1d1f] hover:bg-gray-50 shadow-md transition-colors text-lg leading-none"
              aria-label="지도 줌 인"
            >
              +
            </button>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); zoomOut(); }}
              className="w-9 h-9 flex items-center justify-center rounded-lg bg-white/95 border border-gray-200 text-[#1d1d1f] hover:bg-gray-50 shadow-md transition-colors text-lg leading-none"
              aria-label="지도 줌 아웃"
            >
              −
            </button>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); zoomReset(); }}
              className="w-9 h-9 flex items-center justify-center rounded-lg bg-white/95 border border-gray-200 text-[#1d1d1f] hover:bg-gray-50 shadow-md transition-colors text-xs leading-none"
              aria-label="지도 줌 리셋"
            >
              ⟲
            </button>
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-[10px] font-medium text-[#6e6e73] px-1">마커/글자</span>
          <div className="flex flex-col gap-1">
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); markerLabelZoomIn(); }}
              className="w-9 h-9 flex items-center justify-center rounded-lg bg-white/95 border border-gray-200 text-[#1d1d1f] hover:bg-gray-50 shadow-md transition-colors text-lg leading-none"
              aria-label="마커/글자 줌 인"
            >
              +
            </button>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); markerLabelZoomOut(); }}
              className="w-9 h-9 flex items-center justify-center rounded-lg bg-white/95 border border-gray-200 text-[#1d1d1f] hover:bg-gray-50 shadow-md transition-colors text-lg leading-none"
              aria-label="마커/글자 줌 아웃"
            >
              −
            </button>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); markerLabelZoomReset(); }}
              className="w-9 h-9 flex items-center justify-center rounded-lg bg-white/95 border border-gray-200 text-[#1d1d1f] hover:bg-gray-50 shadow-md transition-colors text-xs leading-none"
              aria-label="마커/글자 줌 리셋"
            >
              ⟲
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
