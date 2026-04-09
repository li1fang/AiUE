#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "PMXCharacterHost.generated.h"

class UPMXCharacterEquipmentComponent;
class UPMXEquipmentLoadoutAsset;
class USkeletalMesh;

UCLASS(BlueprintType, Blueprintable)
class AIUEPMXRUNTIME_API APMXCharacterHost : public ACharacter
{
    GENERATED_BODY()

public:
    APMXCharacterHost();

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    UPMXCharacterEquipmentComponent* EnsureEquipmentComponent();

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    void ApplyConfiguredLoadout();

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    void SetCharacterMeshAsset(USkeletalMesh* InCharacterMeshAsset);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    void SetDefaultLoadoutAsset(UPMXEquipmentLoadoutAsset* InDefaultLoadoutAsset);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    void SetEquipmentComponentClass(TSubclassOf<UPMXCharacterEquipmentComponent> InEquipmentComponentClass);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    UPMXCharacterEquipmentComponent* GetRuntimeEquipmentComponent() const;

protected:
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void BeginPlay() override;

private:
    void ApplyCharacterMesh();

private:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline", meta=(AllowPrivateAccess="true"))
    TObjectPtr<USkeletalMesh> CharacterMeshAsset;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline", meta=(AllowPrivateAccess="true"))
    TObjectPtr<UPMXEquipmentLoadoutAsset> DefaultLoadoutAsset;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline", meta=(AllowPrivateAccess="true"))
    TSubclassOf<UPMXCharacterEquipmentComponent> EquipmentComponentClass;

    UPROPERTY(Transient)
    TObjectPtr<UPMXCharacterEquipmentComponent> RuntimeEquipmentComponent;
};
